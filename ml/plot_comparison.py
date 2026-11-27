"""모델 비교 그림 (REQ-NFR-014, 발표·docs/model-comparison.md용).

compare.py와 같은 분할(층화 80/20, 시드 42)·같은 모델로 평가 세트 확률을 만들고 그림 3장을 그림.
  1. ROC 곡선: 4개 모델 (로지스틱이 단순 기준보다 위, XGBoost와 겹침)
  2. 위험 단계별 실제 위험 비율: 로지스틱의 낮음·주의·높음이 실제로 갈리는지
  3. 보정 곡선: 예측 확률 10구간 평균 vs 실제 비율 (대각선에 가까우면 "34점 = 실제 약 34%")

그림에는 집계(곡선 좌표·구간 평균·비율)만 들어감. 원본 행은 저장하지 않음 (CLAUDE.md 8장).
실행 (맥, 원본은 레포 밖): uv run --env-file envs/.local.env --group ml python -m ml.plot_comparison
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import matplotlib

matplotlib.use("Agg")  # 화면 없이 파일로만

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from ml.compare import MODELS  # noqa: E402
from ml.evaluate import to_level, to_score  # noqa: E402
from ml.train import DISEASES, SEED, TEST_SIZE, build_xy, load_raw, select_target  # noqa: E402

logger = logging.getLogger(__name__)

OUT_DIR: Final = Path("docs/images/model-comparison")
DISEASE_LABELS: Final = {"diabetes": "당뇨 (전단계 이상)", "hypertension": "고혈압 (전단계 이상)"}
MODEL_LABELS: Final = {"logistic": "로지스틱 (서버)", "age_only": "나이만", "age_bmi": "나이+BMI", "xgboost": "XGBoost"}
LEVEL_LABELS: Final = ("낮음\n(0~29점)", "주의\n(30~59점)", "높음\n(60점~)")
N_CALIBRATION_BINS: Final = 10

# 색: dataviz 기본 범주 팔레트 1~4번을 고정 순서로 (validate_palette.js light 통과, 대비 WARN → 범례·표로 보완)
# 모델 = 색 + 선 모양 둘 다로 구분 (색만으로 구분하지 않음)
MODEL_STYLES: Final = {
    "logistic": {"color": "#257de0", "linestyle": "-", "linewidth": 2.4},
    "age_only": {"color": "#f47230", "linestyle": ":", "linewidth": 2.0},
    "age_bmi": {"color": "#00b894", "linestyle": "--", "linewidth": 2.0},
    "xgboost": {"color": "#f2a600", "linestyle": "-.", "linewidth": 2.0},
}
BAR_COLOR: Final = "#257de0"  # 한 계열이라 한 색
TEXT_PRIMARY: Final = "#1f1f1f"
TEXT_SECONDARY: Final = "#6b6b6b"
GRID_COLOR: Final = "#e6e6e6"
REFERENCE_COLOR: Final = "#9c9c9c"
FONT_CANDIDATES: Final = ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR", "Malgun Gothic")


@dataclass(frozen=True)
class LevelOutcome:
    """위험 단계 하나의 평가 세트 집계."""

    count: int
    positive_rate: float  # 그 단계 사람 중 실제 위험(정답 1) 비율, 사람이 없으면 nan


@dataclass(frozen=True)
class CalibrationBins:
    """예측 확률 구간별 평균 예측 확률과 실제 비율."""

    mean_predicted: np.ndarray
    observed_rate: np.ndarray


# ───── 계산 (순수 함수) ─────
def holdout_probabilities(
    x: pd.DataFrame, y: pd.Series, model_names: tuple[str, ...] = tuple(MODELS)
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """compare.py와 같은 분할로 학습 세트 전체에서 학습 → 평가 세트 확률 (CV는 안 함)."""
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    probabilities: dict[str, np.ndarray] = {}
    for name in model_names:
        columns, factory = MODELS[name]
        use = list(columns) if columns else list(x_tr.columns)
        model = factory().fit(x_tr[use], y_tr)  # type: ignore[attr-defined]
        probabilities[name] = model.predict_proba(x_te[use])[:, 1]
    return y_te.to_numpy(), probabilities


def level_outcomes(y: np.ndarray, probability: np.ndarray) -> list[LevelOutcome]:
    """서버와 같은 점수·단계(30/60)로 나눠서 단계마다 사람 수와 실제 위험 비율."""
    level = to_level(to_score(probability))
    outcomes = []
    for code in range(len(LEVEL_LABELS)):
        mask = level == code
        rate = float(y[mask].mean()) if mask.any() else float("nan")
        outcomes.append(LevelOutcome(count=int(mask.sum()), positive_rate=rate))
    return outcomes


def calibration_bins(y: np.ndarray, probability: np.ndarray, n_bins: int = N_CALIBRATION_BINS) -> CalibrationBins:
    """예측 확률 순으로 사람 수가 같은 n_bins 구간 → 구간별 평균 예측과 실제 비율."""
    order = np.argsort(probability, kind="stable")
    groups = [group for group in np.array_split(order, n_bins) if len(group)]
    return CalibrationBins(
        mean_predicted=np.array([probability[group].mean() for group in groups]),
        observed_rate=np.array([y[group].mean() for group in groups]),
    )


# ───── 그림 ─────
def setup_font() -> None:
    """한글 글꼴: 맥 AppleGothic → 없으면 다른 한글 글꼴 → 없으면 기본(글자가 네모로 나올 수 있음)."""
    installed = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    for name in FONT_CANDIDATES:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    else:
        logger.warning("한글 글꼴을 못 찾음: 그림 글자가 깨질 수 있음")
    plt.rcParams["axes.unicode_minus"] = False


def style_axes(ax: Axes, title: str) -> None:
    """회색 격자·축은 뒤로, 위·오른쪽 테두리는 없앰."""
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=12, loc="left")
    ax.grid(color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID_COLOR)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.xaxis.label.set_color(TEXT_SECONDARY)
    ax.yaxis.label.set_color(TEXT_SECONDARY)


def draw_roc(ax: Axes, y: np.ndarray, probabilities: Mapping[str, np.ndarray], title: str) -> None:
    ax.plot([0, 1], [0, 1], color=REFERENCE_COLOR, linewidth=1, linestyle="--", label="무작위 (0.5)")
    for name, probability in probabilities.items():
        fpr, tpr, _ = roc_curve(y, probability)
        auroc = roc_auc_score(y, probability)
        ax.plot(fpr, tpr, label=f"{MODEL_LABELS[name]}  {auroc:.3f}", **MODEL_STYLES[name])  # type: ignore[arg-type]
    style_axes(ax, title)
    ax.set_xlabel("위험 아닌 사람을 위험으로 본 비율 (1 − 특이도)")
    ax.set_ylabel("실제 위험자를 잡은 비율 (민감도)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(title="모델  AUROC", loc="lower right", fontsize=9, title_fontsize=9, frameon=False)


def draw_levels(ax: Axes, outcomes: list[LevelOutcome], title: str) -> None:
    positions = np.arange(len(outcomes))
    rates = [outcome.positive_rate * 100 for outcome in outcomes]
    ax.bar(positions, rates, width=0.6, color=BAR_COLOR)
    for position, outcome in enumerate(outcomes):
        if outcome.count:
            label = f"{outcome.positive_rate:.0%}\n({outcome.count:,}명)"
            ax.text(position, outcome.positive_rate * 100 + 2, label, ha="center", va="bottom",
                    color=TEXT_PRIMARY, fontsize=9)  # fmt: skip
    style_axes(ax, title)
    ax.set_xticks(positions, LEVEL_LABELS)
    ax.set_ylabel("그 단계에서 실제 위험인 사람 (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=False)


def draw_calibration(ax: Axes, bins: CalibrationBins, title: str) -> None:
    ax.plot([0, 100], [0, 100], color=REFERENCE_COLOR, linewidth=1, linestyle="--", label="완벽한 보정")
    ax.plot(bins.mean_predicted * 100, bins.observed_rate * 100, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, label="로지스틱 (10구간)",
            **MODEL_STYLES["logistic"])  # type: ignore[arg-type]  # fmt: skip
    style_axes(ax, title)
    ax.set_xlabel("예측 위험도 평균 (점)")
    ax.set_ylabel("실제 위험 비율 (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left", fontsize=9, frameon=False)


def save_figures(results: Mapping[str, tuple[np.ndarray, dict[str, np.ndarray]]], out_dir: Path) -> list[Path]:
    """질환별 결과로 그림 3장 (질환 2개를 나란히). 저장한 파일 경로를 돌려줌."""
    setup_font()
    out_dir.mkdir(parents=True, exist_ok=True)
    drawers = {
        "roc.png": lambda ax, y, probs, title: draw_roc(ax, y, probs, title),
        "levels.png": lambda ax, y, probs, title: draw_levels(ax, level_outcomes(y, probs["logistic"]), title),
        "calibration.png": lambda ax, y, probs, title: draw_calibration(
            ax, calibration_bins(y, probs["logistic"]), title
        ),
    }
    saved = []
    for file_name, draw in drawers.items():
        fig, axes = plt.subplots(1, len(results), figsize=(6 * len(results), 5), squeeze=False)
        for ax, (disease, (y, probabilities)) in zip(axes[0], results.items(), strict=True):
            draw(ax, y, probabilities, f"{DISEASE_LABELS.get(disease, disease)} · 평가 {len(y):,}명")
        fig.tight_layout()
        path = out_dir / file_name
        fig.savefig(path, dpi=150, facecolor="white")
        plt.close(fig)
        saved.append(path)
    return saved


def main() -> None:
    if "KNHANES_DIR" not in os.environ:
        raise SystemExit("KNHANES_DIR가 없음: envs/.local.env에 넣고 --env-file로 실행")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raw = load_raw(Path(os.environ["KNHANES_DIR"]))
    results = {}
    for disease, cfg in DISEASES.items():
        x, y = build_xy(select_target(raw, disease))
        results[disease] = holdout_probabilities(x[list(cfg.features)], y)  # compare.py와 같은 입력 9개
    for path in save_figures(results, OUT_DIR):
        logger.info("저장: %s", path)


if __name__ == "__main__":
    main()
