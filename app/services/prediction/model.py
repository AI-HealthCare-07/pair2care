"""모델 JSON으로 위험도 점수 계산 (api.md 5-0 "모델 행"). sklearn 없이 표준 라이브러리만 씀.

모델 JSON 모양 (11/24 장성은 합의: 원래 단위 계수 + 학습 평균, 표준화 없음)
{
  "model_version": "diabetes_risk:v1",       # MLflow 등록 이름:버전
  "mlflow_run_id": "...",                    # 어느 실험에서 나온 모델인지 (기록 없는 모델은 배포 안 함)
  "disease": "DIABETES",
  "features": ["sex", "age", "bmi", ...],    # features.FEATURE_NAMES와 같은 12개, 같은 순서
  "intercept": -5.1,
  "coefficients": {"sex": 0.2, ...},         # 이름으로 짝지음 (순서 실수 방지)
  "means": {"sex": 1.5, ...},                # 예측 때 저장하는 factors(기록용)의 학습 데이터 평균
  "means_by_sex": {                          # 선택. 건강 나이·요인 가감 나이용 같은 성별 7문항 평균 (health_age.py)
    "MALE": {"bmi": 24.6, ...}, "FEMALE": {"bmi": 23.1, ...}
  }
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
# factors 후보에서 빼는 입력 (계산에는 그대로 씀)
# - 성별·나이: 바꿀 수 없는 값. factors는 "바꿀 수 있는 것 → 챌린지"로 이어지는 자리인데, 나이는 평균에서 멀면
#   거의 항상 1순위라 체중·음주·흡연이 밀려남. 나이 비교는 건강 나이가 따로 보여 줌 (11/25 장성은 합의)
# - 다른 질환의 가족력: 계수가 작은 음수라 "위험을 낮춤"처럼 보임 (11/24 합의)
NOT_CHANGEABLE_FIELDS: Final = frozenset({"sex", "age"})
FACTOR_EXCLUDED_BY_DISEASE: Final[dict[Disease, frozenset[str]]] = {
    Disease.DIABETES: NOT_CHANGEABLE_FIELDS | frozenset(HYPERTENSION_FAMILY_FIELDS),
    Disease.HYPERTENSION: NOT_CHANGEABLE_FIELDS | frozenset(DIABETES_FAMILY_FIELDS),
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
        """예측 때 저장하는 factors(기록용): 계수 × (사용자 값 − 학습 평균)의 절댓값 상위 3개.

        응답의 factors는 조회 때 health_age.explain_row가 같은 성별 평균 기준으로 다시 계산함 (api.md 5-0, #114).
        """
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
    model = LogisticModel.from_dict(read_model_file(disease))
    if model.disease != disease:
        raise ValueError(f"{MODEL_FILE_BY_DISEASE[disease]}의 disease가 {disease}가 아님")
    return model


def read_model_file(disease: Disease) -> dict[str, Any]:
    path = MODEL_DIR / MODEL_FILE_BY_DISEASE[disease]
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
