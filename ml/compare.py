"""모델 가치 증명 비교 (REQ-NFR-014, 11/25 멘토링 후속 · 최현영).

같은 데이터·같은 분할에서 우리 로지스틱이 단순 기준보다 나은지, XGBoost와 차이가 있는지 숫자로 보여 줌.

실행 (레포 루트에서, 원본 위치는 envs/.local.env의 KNHANES_DIR):
    uv run --env-file envs/.local.env --group ml python -m ml.compare

- 데이터·분할은 train.py와 같은 함수(select_target·build_xy, 층화 80/20, 시드 42)를 그대로 씀
- 비교 모델: 로지스틱 / 나이만 / 나이+BMI / XGBoost. 로지스틱·XGBoost는 질환별 입력 9개
  (train.py DiseaseConfig.features, 다른 질환 가족력 제외 — 서버 모델과 같은 입력이라야 공정한 비교)
- 지표: 학습 세트 5-fold CV AUROC, 평가 세트 AUROC(부트스트랩 95% 신뢰구간)·AUPRC·Brier·보정 기울기,
  성별별 AUROC(신뢰구간), 위험 단계 지표(evaluate.level_metrics), 로지스틱 대비 AUROC 차이(짝지은 부트스트랩)
- 원본·개별 자료는 출력·MLflow에 남기지 않음. 집계 숫자만
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import mlflow
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ml.evaluate import basic_metrics, level_metrics
from ml.train import (
    DISEASES,
    SEED,
    TEST_SIZE,
    YEARS,
    build_xy,
    file_sha256,
    load_raw,
    make_logit,
    raw_path,
    select_target,
    setup_mlflow,
)

N_BOOTSTRAP: Final = 1000
CONFIDENCE: Final = 0.95
BASE_MODEL: Final = "logistic"
SEX_LABELS: Final = {1: "male", 2: "female"}  # features.py sex 코드


ModelFactory = Callable[[], object]


def make_simple_logit() -> object:
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))


def make_xgboost() -> object:
    """성은님 노트북(11/24) 비교와 같은 성격의 얕은 트리. 튜닝 없이 고정값 (시드 42)."""
    return XGBClassifier(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=SEED,
        n_jobs=1,
        eval_metric="logloss",
    )


# 모델 이름 → (쓸 입력 컬럼, 모델 만드는 함수). None이면 넘겨받은 입력 전부 (main에서는 질환별 9개)
MODELS: Final[dict[str, tuple[tuple[str, ...] | None, ModelFactory]]] = {
    BASE_MODEL: (None, make_logit),
    "age_only": (("age",), make_simple_logit),
    "age_bmi": (("age", "bmi"), make_simple_logit),
    "xgboost": (None, make_xgboost),
}


# ───── 신뢰구간 ─────
def bootstrap_indices(n_rows: int, n_bootstrap: int, seed: int) -> np.ndarray:
    """평가 세트 행 번호를 복원 추출한 (n_bootstrap, n_rows) 배열. 모델끼리 같은 표본을 쓰려고 미리 만듦."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_rows, size=(n_bootstrap, n_rows))


def auroc_samples(y: np.ndarray, probability: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """표본마다 AUROC. 한 클래스만 뽑힌 표본은 nan (신뢰구간 계산에서 뺌)."""
    values = np.full(len(indices), np.nan)
    for i, rows in enumerate(indices):
        y_sample = y[rows]
        if y_sample.min() != y_sample.max():
            values[i] = roc_auc_score(y_sample, probability[rows])
    return values


def percentile_interval(samples: np.ndarray) -> tuple[float, float]:
    valid = samples[~np.isnan(samples)]
    tail = (1 - CONFIDENCE) / 2 * 100
    return float(np.percentile(valid, tail)), float(np.percentile(valid, 100 - tail))


def auroc_with_interval(y: np.ndarray, probability: np.ndarray, indices: np.ndarray) -> dict[str, float]:
    low, high = percentile_interval(auroc_samples(y, probability, indices))
    return {"auroc": float(roc_auc_score(y, probability)), "auroc_ci_low": low, "auroc_ci_high": high}


def auroc_difference(
    y: np.ndarray, probability: np.ndarray, base_probability: np.ndarray, indices: np.ndarray
) -> dict[str, float]:
    """같은 표본에서 (이 모델 − 기준 모델) AUROC 차이. 신뢰구간이 0을 넘지 않으면 '차이 없음'."""
    diff = auroc_samples(y, probability, indices) - auroc_samples(y, base_probability, indices)
    low, high = percentile_interval(diff)
    point = float(roc_auc_score(y, probability) - roc_auc_score(y, base_probability))
    return {"auroc_diff_vs_logistic": point, "auroc_diff_ci_low": low, "auroc_diff_ci_high": high}


def metrics_by_sex(
    y: np.ndarray, probability: np.ndarray, sex: np.ndarray, n_bootstrap: int, seed: int
) -> dict[str, float]:
    """성별별 AUROC + 신뢰구간, 성별별 위험 비율·평균 예측 (멘토링: 성별별 지표)."""
    out: dict[str, float] = {}
    for code, label in SEX_LABELS.items():
        mask = sex == code
        if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
            continue
        y_sex, p_sex = y[mask], probability[mask]
        indices = bootstrap_indices(len(y_sex), n_bootstrap, seed)
        result = auroc_with_interval(y_sex, p_sex, indices)
        out[f"auroc_{label}"] = result["auroc"]
        out[f"auroc_{label}_ci_low"] = result["auroc_ci_low"]
        out[f"auroc_{label}_ci_high"] = result["auroc_ci_high"]
        out[f"n_test_{label}"] = float(mask.sum())
        out[f"positive_rate_{label}"] = float(y_sex.mean())
        out[f"mean_pred_{label}"] = float(p_sex.mean())
    return out


# ───── 비교 ─────
def fit_predict(
    name: str, x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """학습 세트 5-fold CV AUROC + 학습 세트 전체로 학습한 모델의 평가 세트 확률."""
    columns, factory = MODELS[name]
    use = list(columns) if columns else list(x_train.columns)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_auroc = cross_val_score(factory(), x_train[use], y_train, cv=cv, scoring="roc_auc")
    model = factory().fit(x_train[use], y_train)  # type: ignore[attr-defined]
    return cv_auroc, model.predict_proba(x_test[use])[:, 1]


def compare_models(
    x: pd.DataFrame, y: pd.Series, n_bootstrap: int = N_BOOTSTRAP, model_names: tuple[str, ...] = tuple(MODELS)
) -> dict[str, dict[str, float]]:
    """모델마다 집계 지표 dict. train.py evaluate_holdout과 같은 분할."""
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    y_test = y_te.to_numpy()
    sex = x_te["sex"].to_numpy()
    indices = bootstrap_indices(len(y_test), n_bootstrap, SEED)

    probabilities: dict[str, np.ndarray] = {}
    results: dict[str, dict[str, float]] = {}
    for name in model_names:
        cv_auroc, probability = fit_predict(name, x_tr, y_tr, x_te)
        probabilities[name] = probability
        results[name] = {
            "cv_auroc_mean": float(cv_auroc.mean()),
            "cv_auroc_std": float(cv_auroc.std()),
            **basic_metrics(y_test, probability),
            **auroc_with_interval(y_test, probability, indices),
            **metrics_by_sex(y_test, probability, sex, n_bootstrap, SEED),
            **level_metrics(y_test, probability),
        }
    if BASE_MODEL in probabilities:
        for name in model_names:
            if name != BASE_MODEL:
                results[name].update(auroc_difference(y_test, probabilities[name], probabilities[BASE_MODEL], indices))
    return results


# ───── 출력 ─────
SUMMARY_COLUMNS: Final = (
    ("cv_auroc_mean", "CV AUROC"),
    ("auroc", "평가 AUROC"),
    ("auprc", "AUPRC"),
    ("brier", "Brier"),
    ("calibration_slope", "보정 기울기"),
    ("auroc_male", "남 AUROC"),
    ("auroc_female", "여 AUROC"),
    ("recall_caution_or_high", "주의 이상 Recall"),
    ("precision_high", "높음 Precision"),
)


def format_interval(metrics: Mapping[str, float], key: str) -> str:
    value = metrics.get(key)
    if value is None:
        return "-"
    low, high = metrics.get(f"{key}_ci_low"), metrics.get(f"{key}_ci_high")
    if low is None or high is None:
        return f"{value:.3f}"
    return f"{value:.3f} ({low:.3f}~{high:.3f})"


def summary_table(results: Mapping[str, Mapping[str, float]]) -> str:
    """집계 숫자만 담은 마크다운 표 (보고서·PR에 그대로 붙임)."""
    header = "| 모델 | " + " | ".join(label for _, label in SUMMARY_COLUMNS) + " | 로지스틱 대비 AUROC 차이 |"
    lines = [header, "|" + "---|" * (len(SUMMARY_COLUMNS) + 2)]
    for name, metrics in results.items():
        cells = [format_interval(metrics, key) for key, _ in SUMMARY_COLUMNS]
        if "auroc_diff_vs_logistic" in metrics:
            diff = (
                f"{metrics['auroc_diff_vs_logistic']:+.3f} "
                f"({metrics['auroc_diff_ci_low']:+.3f}~{metrics['auroc_diff_ci_high']:+.3f})"
            )
        else:
            diff = "기준"
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {diff} |")
    return "\n".join(lines)


def flatten_metrics(results: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """MLflow 이름: <모델>_<지표>."""
    return {f"{name}_{key}": value for name, metrics in results.items() for key, value in metrics.items()}


def main() -> None:
    if "KNHANES_DIR" not in os.environ:
        raise SystemExit("KNHANES_DIR가 없음: envs/.local.env에 넣고 --env-file로 실행")
    knhanes_dir = Path(os.environ["KNHANES_DIR"])
    setup_mlflow()
    data_tags = {f"data_sha256_{year}": file_sha256(raw_path(knhanes_dir, year)) for year in YEARS}
    raw = load_raw(knhanes_dir)

    for disease, cfg in DISEASES.items():
        x, y = build_xy(select_target(raw, disease))
        x = x[list(cfg.features)]  # 서버 모델과 같은 입력 9개 (로지스틱·XGBoost)
        with mlflow.start_run(run_name=f"compare:{cfg.model_version}"):
            results = compare_models(x, y)
            mlflow.log_params({"disease": cfg.code, "models": ",".join(MODELS), "n_bootstrap": N_BOOTSTRAP})
            mlflow.set_tags({**data_tags, "kind": "model_comparison"})
            mlflow.log_metrics({"n_total": float(len(x)), **flatten_metrics(results)})
            table = summary_table(results)
            mlflow.log_text(table, f"compare_{disease}.md")
        print(f"\n## {cfg.code} ({len(x)}명, 위험 {y.mean():.1%})\n{table}")


if __name__ == "__main__":
    main()
