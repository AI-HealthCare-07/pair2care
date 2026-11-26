"""예측 모델 학습 → 서버 JSON + MLflow 기록 (baseline.ipynb 셀 1–5·13·14를 코드로 옮김).

실행 (레포 루트에서, 원본 위치는 envs/.local.env의 KNHANES_DIR):
    uv run --env-file envs/.local.env --group ml python -m ml.train

흐름: 원본 불러오기 → 대상·정답 → 입력 변환(features.py) → 80/20 분할(시드 42)
      → 학습 세트 5-fold CV + 평가 세트 지표 → 100% 재학습 → 서버 JSON(+ 같은 성별 평균) → MLflow
- 원본·개별 자료는 레포·MLflow에 남기지 않음. 출력·기록은 인원·비율·지표·계수만
- 결과 JSON은 MLflow artifacts(mlruns/, .gitignore)에 저장. 레포 model_files/ 교체는 따로 PR
"""

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import mlflow
import numpy as np
import pandas as pd
import pyreadstat
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from app.models.risk_predictions import Disease
from app.services.prediction.features import (
    DIABETES_FAMILY_FIELDS,
    FEATURE_NAMES,
    HYPERTENSION_FAMILY_FIELDS,
    MAX_AGE,
    MIN_AGE,
    to_model_inputs,
)
from ml.evaluate import basic_metrics, count_wrong_sign, level_metrics, metrics_by_age
from ml.serving_json import build_means_by_sex, health_age_fields, to_server_json

YEARS: Final = (2022, 2023, 2024)
SEED: Final = 42
TEST_SIZE: Final = 0.2
C: Final = 1.0  # 규제 강도 (셀 12: 0.01~100 모두 같은 성능)
EXPERIMENT: Final = "pair2care-risk"

# 국건영 원자료 컬럼 → 앱 저장값 이름 (survey-mapping.md, 값은 같은 코드)
RAW_TO_APP: Final = {
    "sex": "sex",
    "age": "age",
    "HE_ht": "height_cm",
    "HE_wt": "weight_kg",
    "HE_DMfh1": "father_diabetes_history",
    "HE_DMfh2": "mother_diabetes_history",
    "HE_DMfh3": "sibling_diabetes_history",
    "HE_HPfh1": "father_hypertension_history",
    "HE_HPfh2": "mother_hypertension_history",
    "HE_HPfh3": "sibling_hypertension_history",
    "BD1_11": "alcohol_frequency",
    "BD2_1": "alcohol_amount",
    "BS3_1": "smoking_current",
}
FAMILY_RAW: Final = ("HE_DMfh1", "HE_DMfh2", "HE_DMfh3", "HE_HPfh1", "HE_HPfh2", "HE_HPfh3")
RAW_COLUMNS: Final = (*RAW_TO_APP, "HE_DM_HbA1c", "HE_sbp", "HE_dbp", "DE1_dg", "DI1_dg", "HE_prg")


@dataclass(frozen=True)
class DiseaseConfig:
    code: str  # 서버 Disease 값
    model_version: str
    file_name: str
    own_family_fields: tuple[str, ...]


DISEASES: Final = {
    "diabetes": DiseaseConfig("DIABETES", "diabetes_risk:v1", "diabetes.json", DIABETES_FAMILY_FIELDS),
    "hypertension": DiseaseConfig(
        "HYPERTENSION", "hypertension_risk:v1", "hypertension.json", HYPERTENSION_FAMILY_FIELDS
    ),
}


# ───── 데이터 ─────
def raw_path(knhanes_dir: Path, year: int) -> Path:
    yy = str(year)[2:]
    return knhanes_dir / f"HN{yy}_ALL(SAS)" / f"hn{yy}_all.sas7bdat"


def file_sha256(path: Path) -> str:
    """원본 파일 버전 확인용 해시 (내용은 기록하지 않음)."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_raw(knhanes_dir: Path) -> pd.DataFrame:
    frames = []
    for year in YEARS:
        df, _ = pyreadstat.read_sas7bdat(str(raw_path(knhanes_dir, year)), usecols=list(RAW_COLUMNS), encoding="cp949")
        missing = sorted(set(RAW_COLUMNS) - set(df.columns))
        if missing:
            raise ValueError(f"{year}년 원본에 없는 컬럼: {missing}")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def keep_complete(df: pd.DataFrame) -> pd.DataFrame:
    """예측 문항이 앱 보기 범위 안에 있는 사람만 (가족력 모름 9는 남김 → features.py가 0으로)."""
    is_ok = df["HE_ht"].notna() & df["HE_wt"].notna() & df["sex"].isin([1, 2])
    for col in FAMILY_RAW:
        allowed = [0, 1, 9, 8] if col.endswith("fh3") else [0, 1, 9]
        is_ok &= df[col].isin(allowed)
    is_ok &= df["BD1_11"].isin([1, 2, 3, 4, 5, 6, 8]) & df["BD2_1"].isin([1, 2, 3, 4, 5, 8])
    is_ok &= df["BS3_1"].isin([1, 2, 3, 8])
    return df[is_ok].copy()


def select_target(raw: pd.DataFrame, disease: str) -> pd.DataFrame:
    """30~69세, 임신 제외, 해당 질환 진단자 제외 + 정답 y (ml/README.md 기준)."""
    base = raw[raw["age"].between(MIN_AGE, MAX_AGE) & raw["HE_prg"].ne(1)]
    if disease == "diabetes":
        # 공복혈당 100 이상 또는 당화혈색소 5.7% 이상 = HE_DM_HbA1c 2·3
        df = base[base["DE1_dg"].eq(0) & base["HE_DM_HbA1c"].isin([1, 2, 3])].copy()
        df["y"] = (df["HE_DM_HbA1c"] >= 2).astype(int)
    else:
        df = base[base["DI1_dg"].eq(0) & base["HE_sbp"].notna() & base["HE_dbp"].notna()].copy()
        df["y"] = ((df["HE_sbp"] >= 130) | (df["HE_dbp"] >= 80)).astype(int)
    return keep_complete(df)


def build_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """원자료 → 앱 저장값 이름 → features.py로 모델 입력 12개 (서빙과 같은 변환, bmi 반올림 포함)."""
    app = df[list(RAW_TO_APP)].rename(columns=RAW_TO_APP)
    rows = [to_model_inputs(int(r["sex"]), int(r["age"]), r) for r in app.to_dict("records")]
    x = pd.DataFrame(rows, index=app.index, columns=list(FEATURE_NAMES))
    return x, df["y"].astype(int)


# ───── 모델 ─────
def make_logit() -> Pipeline:
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000))


def to_original_units(model: Pipeline) -> tuple[float, dict[str, float], dict[str, float]]:
    """표준화한 계수 → 원래 단위 계수 (서버는 표준화 없이 계산). means = 학습 데이터 평균 (factors용)."""
    scaler, logit = model[0], model[-1]
    coef_scaled = logit.coef_[0]
    coef = coef_scaled / scaler.scale_
    intercept = float(logit.intercept_[0] - np.sum(coef_scaled * scaler.mean_ / scaler.scale_))
    names = list(FEATURE_NAMES)
    coefficients = {name: float(value) for name, value in zip(names, coef, strict=True)}
    means = {name: float(value) for name, value in zip(names, scaler.mean_, strict=True)}
    return intercept, coefficients, means


def server_probability(spec: dict[str, Any], x: pd.DataFrame) -> np.ndarray:
    """서버 model.py와 같은 계산 (이름으로 계수를 짝지어 sigmoid)."""
    z = spec["intercept"] + sum(spec["coefficients"][name] * x[name].to_numpy() for name in FEATURE_NAMES)
    return 1 / (1 + np.exp(-z))


def evaluate_holdout(x: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """80% 학습 / 20% 평가 (층화, 시드 42). 학습 세트 5-fold CV + 평가 세트 지표."""
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_auroc = cross_val_score(make_logit(), x_tr, y_tr, cv=cv, scoring="roc_auc")
    p_te = make_logit().fit(x_tr, y_tr).predict_proba(x_te)[:, 1]
    y_te_arr = y_te.to_numpy()

    metrics: dict[str, float] = {
        "n_train": len(x_tr),
        "n_test": len(x_te),
        "cv_auroc_mean": float(cv_auroc.mean()),
        "cv_auroc_std": float(cv_auroc.std()),
    }
    test_metrics = {
        **basic_metrics(y_te_arr, p_te),
        **metrics_by_age(y_te_arr, p_te, x_te["age"].to_numpy()),
        **level_metrics(y_te_arr, p_te),
    }
    metrics.update({f"test_{name}": value for name, value in test_metrics.items()})
    return metrics


def fit_final(x: pd.DataFrame, y: pd.Series, cfg: DiseaseConfig, run_id: str) -> dict[str, Any]:
    """100% 데이터로 다시 학습 → 서버 JSON. JSON 계산이 sklearn과 같은지 확인."""
    model = make_logit().fit(x, y)
    intercept, coefficients, means = to_original_units(model)
    spec = to_server_json(
        model_version=cfg.model_version,
        disease=cfg.code,
        intercept=intercept,
        coefficients=coefficients,
        means=means,
        mlflow_run_id=run_id,
    )
    gap = float(np.abs(server_probability(spec, x) - model.predict_proba(x)[:, 1]).max())
    if gap > 1e-9:
        raise ValueError(f"{cfg.code}: JSON 계산이 sklearn과 다름 (최대 차이 {gap:.2e})")
    return spec


# ───── 실행 ─────
def train_one(
    raw: pd.DataFrame, disease: str, cfg: DiseaseConfig, data_tags: dict[str, str], out_dir: Path | None
) -> None:
    x, y = build_xy(select_target(raw, disease))
    with mlflow.start_run(run_name=cfg.model_version) as run:
        metrics = {"n_total": float(len(x)), "positive_rate": float(y.mean()), **evaluate_holdout(x, y)}
        spec = fit_final(x, y, cfg, run.info.run_id)
        wrong = count_wrong_sign(spec["coefficients"], cfg.own_family_fields)
        metrics["wrong_sign_count"] = float(wrong)

        mlflow.log_params(
            {
                "disease": cfg.code,
                "model_version": cfg.model_version,
                "years": ",".join(map(str, YEARS)),
                "age_range": f"{MIN_AGE}-{MAX_AGE}",
                "seed": SEED,
                "test_size": TEST_SIZE,
                "C": C,
                "features": ",".join(FEATURE_NAMES),
            }
        )
        mlflow.set_tags(data_tags)
        mlflow.log_metrics(metrics)
        if wrong:
            # 계수 방향이 진료지침과 반대면 원인 확인 전에는 JSON을 만들지 않음 (CLAUDE.md 모델 규칙)
            raise ValueError(f"{cfg.code}: 계수 부호가 진료지침과 반대인 입력 {wrong}개")

        spec["means_by_sex"] = build_means_by_sex(x.to_dict("records"), health_age_fields(Disease(cfg.code)))
        mlflow.log_dict(spec, cfg.file_name)
        mlflow.log_dict({"coefficients": spec["coefficients"], "intercept": spec["intercept"]}, "coefficients.json")
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / cfg.file_name).write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        print(
            f"{cfg.code}: {len(x)}명 (위험 {y.mean():.1%}) | CV AUROC {metrics['cv_auroc_mean']:.4f} "
            f"| 평가 AUROC {metrics['test_auroc']:.4f} | 부호 위반 {wrong} | run {run.info.run_id}"
        )


def setup_mlflow() -> None:
    """MLflow 기록 위치: 레포의 mlruns/ 안 (sqlite + artifacts, .gitignore로 git에 안 올라감)."""
    if "MLFLOW_TRACKING_URI" not in os.environ:
        mlruns = Path("mlruns").resolve()
        mlruns.mkdir(exist_ok=True)
        mlflow.set_tracking_uri(f"sqlite:///{(mlruns / 'mlflow.db').as_posix()}")
        if mlflow.get_experiment_by_name(EXPERIMENT) is None:
            mlflow.create_experiment(EXPERIMENT, artifact_location=(mlruns / "artifacts").as_uri())
    mlflow.set_experiment(EXPERIMENT)


def main() -> None:
    parser = argparse.ArgumentParser(description="고혈압·당뇨 위험 예측 모델 학습")
    parser.add_argument("--out-dir", type=Path, default=None, help="서버 JSON을 여기에도 저장 (레포 밖 폴더 권장)")
    args = parser.parse_args()

    if "KNHANES_DIR" not in os.environ:
        raise SystemExit("KNHANES_DIR가 없음: envs/.local.env에 넣고 --env-file로 실행")
    knhanes_dir = Path(os.environ["KNHANES_DIR"])
    setup_mlflow()

    data_tags = {f"data_sha256_{year}": file_sha256(raw_path(knhanes_dir, year)) for year in YEARS}
    raw = load_raw(knhanes_dir)
    data_tags["data_rows_raw"] = str(len(raw))
    print(f"원본 {len(raw)}명 ({YEARS[0]}~{YEARS[-1]})")

    for disease, cfg in DISEASES.items():
        train_one(raw, disease, cfg, data_tags, args.out_dir)


if __name__ == "__main__":
    main()
