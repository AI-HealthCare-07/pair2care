"""모델 JSON으로 위험도 점수 계산 (api.md 5-0 "모델 행"). sklearn 없이 표준 라이브러리만 씀.

모델 JSON 모양 (11/24 장성은 합의: 원래 단위 계수 + 학습 평균, 표준화 없음)
{
  "model_version": "diabetes_risk:v1",       # MLflow 등록 이름:버전
  "mlflow_run_id": "...",                    # 어느 실험에서 나온 모델인지 (기록 없는 모델은 배포 안 함)
  "disease": "DIABETES",
  "features": ["sex", "age", "bmi", ...],    # features.FEATURE_NAMES와 같은 12개, 같은 순서
  "intercept": -5.1,
  "coefficients": {"sex": 0.2, ...},         # 이름으로 짝지음 (순서 실수 방지)
  "means": {"sex": 1.5, ...}                 # factors 계산용 학습 데이터 평균
}
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from app.models.risk_predictions import Disease, RiskLevel
from app.services.prediction.features import (
    DIABETES_FAMILY_FIELDS,
    FEATURE_NAMES,
    HYPERTENSION_FAMILY_FIELDS,
)

MODEL_DIR: Final = Path(__file__).parent / "model_files"
MODEL_FILE_BY_DISEASE: Final = {Disease.DIABETES: "diabetes.json", Disease.HYPERTENSION: "hypertension.json"}

# 위험 단계: 반올림한 정수 score로 나눔 (api.md 5-0, 11/24 확정 30 / 60)
CAUTION_MIN_SCORE: Final = 30
HIGH_MIN_SCORE: Final = 60

FACTOR_COUNT: Final = 3
# factors 후보에서 빼는 입력 (계산에는 그대로 씀): 바꿀 수 없는 성별, 다른 질환의 가족력 (11/24 합의)
FACTOR_EXCLUDED_BY_DISEASE: Final[dict[Disease, frozenset[str]]] = {
    Disease.DIABETES: frozenset({"sex", *HYPERTENSION_FAMILY_FIELDS}),
    Disease.HYPERTENSION: frozenset({"sex", *DIABETES_FAMILY_FIELDS}),
}


@dataclass(frozen=True)
class LogisticModel:
    model_version: str
    disease: Disease
    intercept: float
    coefficients: dict[str, float]
    means: dict[str, float]
    mlflow_run_id: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LogisticModel":
        """JSON 내용을 검사하고 모델로. 입력 이름·순서가 features.py와 다르면 ValueError (학습·서빙 어긋남 방지)."""
        if tuple(data["features"]) != FEATURE_NAMES:
            raise ValueError(f"모델 features가 FEATURE_NAMES와 다름: {data['features']}")
        coefficients = {name: float(data["coefficients"][name]) for name in FEATURE_NAMES}
        means = {name: float(data["means"][name]) for name in FEATURE_NAMES}
        return cls(
            model_version=str(data["model_version"]),
            disease=Disease(data["disease"]),
            intercept=float(data["intercept"]),
            coefficients=coefficients,
            means=means,
            mlflow_run_id=data.get("mlflow_run_id"),
        )

    def probability(self, model_inputs: Mapping[str, float]) -> float:
        logit = self.intercept + sum(self.coefficients[name] * float(model_inputs[name]) for name in FEATURE_NAMES)
        return 1 / (1 + math.exp(-logit))

    def factors(self, model_inputs: Mapping[str, float]) -> list[dict[str, str]]:
        """계수 × (사용자 값 − 학습 평균)의 절댓값 상위 3개. 양수 UP / 음수 DOWN, 0은 뺌."""
        excluded = FACTOR_EXCLUDED_BY_DISEASE[self.disease]
        contributions = [
            (name, self.coefficients[name] * (float(model_inputs[name]) - self.means[name]))
            for name in FEATURE_NAMES
            if name not in excluded
        ]
        ranked = sorted((item for item in contributions if item[1] != 0), key=lambda item: abs(item[1]), reverse=True)
        return [{"feature": name, "direction": "UP" if value > 0 else "DOWN"} for name, value in ranked[:FACTOR_COUNT]]


def to_score(probability: float) -> int:
    """확률 × 100을 0~100 정수로 (0.5는 올림, 파이썬 round의 짝수 반올림을 쓰지 않음)."""
    return min(100, max(0, math.floor(probability * 100 + 0.5)))


def to_level(score: int) -> RiskLevel:
    if score >= HIGH_MIN_SCORE:
        return RiskLevel.HIGH
    if score >= CAUTION_MIN_SCORE:
        return RiskLevel.CAUTION
    return RiskLevel.LOW


@cache
def load_model(disease: Disease) -> LogisticModel:
    """질환별 모델 JSON을 한 번만 읽음 (서버가 떠 있는 동안 캐시)."""
    path = MODEL_DIR / MODEL_FILE_BY_DISEASE[disease]
    model = LogisticModel.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if model.disease != disease:
        raise ValueError(f"{path.name}의 disease가 {disease}가 아님")
    return model
