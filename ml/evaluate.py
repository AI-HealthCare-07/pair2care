"""모델 평가 지표 (baseline.ipynb 셀 5·6·9·12·13을 코드로 옮김). MLflow metrics로 기록.

- 평가 수치는 80% 학습 / 20% 평가 세트로 계산 (100% 재학습 모델로 평가 세트를 다시 재지 않음)
- 점수·위험 단계는 서버(app/services/prediction/model.py)와 같은 규칙. 같은지는 app/tests/ml 테스트가 확인
"""

from collections.abc import Mapping
from typing import Final

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

# 서버 model.py와 같은 값 (api.md 5-0, 11/24 확정)
CAUTION_MIN_SCORE: Final = 30
HIGH_MIN_SCORE: Final = 60

AGE_BANDS: Final = ((30, 39), (40, 49), (50, 59), (60, 69))

# 계수 부호 기대 방향 (진료지침): 반드시 양수 / 0 이상
MUST_BE_POSITIVE_COMMON: Final = ("age", "bmi", "alcohol_frequency", "alcohol_amount")
MUST_BE_NON_NEGATIVE: Final = ("smoking_current",)


def to_score(probability: np.ndarray) -> np.ndarray:
    """서버 to_score와 같음: 확률 × 100, 0.5 올림, 0~100 정수."""
    return np.clip(np.floor(probability * 100 + 0.5), 0, 100).astype(int)


def to_level(score: np.ndarray) -> np.ndarray:
    """0 LOW / 1 CAUTION / 2 HIGH (반올림한 정수 score로 판정)."""
    return np.where(score >= HIGH_MIN_SCORE, 2, np.where(score >= CAUTION_MIN_SCORE, 1, 0))


def calibration_slope(y: np.ndarray, probability: np.ndarray) -> float:
    """보정 기울기: logit(예측 확률)로 실제 정답을 다시 맞춘 계수. 1에 가까우면 보정 잘 됨."""
    p = np.clip(probability, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    return float(LogisticRegression(C=1e6, max_iter=2000).fit(logit, y).coef_[0][0])


def basic_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    return {
        "auroc": float(roc_auc_score(y, probability)),
        "auprc": float(average_precision_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
        "brier_mean_only": float(brier_score_loss(y, np.full(len(y), y.mean()))),
        "mean_pred": float(probability.mean()),
        "positive_rate": float(y.mean()),
        "calibration_slope": calibration_slope(y, probability),
    }


def metrics_by_age(y: np.ndarray, probability: np.ndarray, age: np.ndarray) -> dict[str, float]:
    """연령대별 AUROC (60대 변별력이 낮은 것을 기록, 보고서 한계)."""
    out: dict[str, float] = {}
    for low, high in AGE_BANDS:
        mask = (age >= low) & (age <= high)
        if mask.sum() > 0 and len(np.unique(y[mask])) == 2:
            out[f"auroc_age_{low}s"] = float(roc_auc_score(y[mask], probability[mask]))
    return out


def level_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    """위험 단계(30 / 60)별 비율·실제 위험 비율, CAUTION 이상 Recall, HIGH Precision."""
    level = to_level(to_score(probability))
    out: dict[str, float] = {}
    for code, name in enumerate(("low", "caution", "high")):
        mask = level == code
        out[f"share_{name}"] = float(mask.mean())
        if mask.any():
            out[f"positive_rate_{name}"] = float(y[mask].mean())
    if y.sum() > 0:
        out["recall_caution_or_high"] = float(((level >= 1) & (y == 1)).sum() / y.sum())
    if (level == 2).any():
        out["precision_high"] = float(y[level == 2].mean())
    return out


def count_wrong_sign(coefficients: Mapping[str, float], own_family_fields: tuple[str, ...]) -> int:
    """진료지침과 부호가 반대인 계수 수 (0이어야 함). 해당 질환 가족력도 양수여야 함."""
    must_be_positive = (*MUST_BE_POSITIVE_COMMON, *own_family_fields)
    wrong = sum(1 for name in must_be_positive if coefficients[name] <= 0)
    wrong += sum(1 for name in MUST_BE_NON_NEGATIVE if coefficients[name] < 0)
    return wrong
