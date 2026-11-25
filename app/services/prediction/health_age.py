"""건강 나이 (api.md 5-2·5-3, 11/25 확정): 내 예측 확률과 같은 확률이 나오는 "아직 진단받지 않은 같은 성별 또래"의 나이.

- 곡선: 모델 JSON의 health_age_curve. 성별마다 30~69세 정수 40개, 확률 0~1, 같은 값 없이 계속 커짐 (장성은)
- 표시: 10살 단위만 (개인 오차가 ±10세라 초반·후반은 1점에도 칸이 자주 바뀜). 문구는 프론트
- 확률은 저장된 score / 100을 씀 → 같은 점수면 언제나 같은 건강 나이
DB 없이 쓰는 순수 함수.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from typing import Any, Final

from app.models.risk_predictions import PredictionMethod, RiskPrediction
from app.services.prediction.features import MAX_AGE, MIN_AGE, SEX_CODE_BY_LABEL

CURVE_AGES: Final = tuple(range(MIN_AGE, MAX_AGE + 1))  # 30~69, 40개


class OutOfRange(StrEnum):
    BELOW = "BELOW"  # 30세 미만 수준
    ABOVE = "ABOVE"  # 69세 초과 수준


@dataclass(frozen=True)
class HealthAgeCurve:
    model_version: str  # 이 곡선을 만든 모델 (다른 버전 점수에는 쓰지 않음)
    probabilities_by_sex: dict[str, tuple[float, ...]]  # "MALE"/"FEMALE" → 30~69세 순서의 확률 40개


def parse_health_age_curve(model_version: str, curve: Mapping[str, Any]) -> HealthAgeCurve:
    """JSON의 health_age_curve 검사. 어긋나면 ValueError (CI 테스트가 이걸로 막음)."""
    probabilities_by_sex: dict[str, tuple[float, ...]] = {}
    for sex in SEX_CODE_BY_LABEL:
        points = curve.get(sex)
        if not isinstance(points, list):
            raise ValueError(f"health_age_curve에 {sex}가 없음")
        ages = tuple(int(point["age"]) for point in points)
        if ages != CURVE_AGES:
            raise ValueError(f"{sex} 곡선 나이가 30~69 정수 40개가 아님")
        probabilities = tuple(float(point["probability"]) for point in points)
        if not all(0 <= value <= 1 for value in probabilities):
            raise ValueError(f"{sex} 곡선에 0~1 밖의 확률이 있음")
        if not all(before < after for before, after in pairwise(probabilities)):
            raise ValueError(f"{sex} 곡선이 같은 값 없이 계속 커지지 않음")
        probabilities_by_sex[sex] = probabilities
    return HealthAgeCurve(model_version=model_version, probabilities_by_sex=probabilities_by_sex)


def estimate_health_age(curve: HealthAgeCurve, sex: str, probability: float, actual_age: int) -> dict[str, Any]:
    """확률 → 곡선에서 같은 확률의 나이(직선 보간) → 10살 단위. 곡선 밖이면 decade 없이 BELOW·ABOVE."""
    probabilities = curve.probabilities_by_sex[sex]
    if probability < probabilities[0]:
        return health_age_body(None, actual_age, OutOfRange.BELOW)
    if probability > probabilities[-1]:
        return health_age_body(None, actual_age, OutOfRange.ABOVE)

    age = float(CURVE_AGES[-1])
    for index, (lower, upper) in enumerate(pairwise(probabilities)):
        if lower <= probability <= upper:
            age = CURVE_AGES[index] + (probability - lower) / (upper - lower)
            break
    return health_age_body(int(age) // 10 * 10, actual_age, None)


def health_age_body(decade: int | None, actual_age: int, out_of_range: OutOfRange | None) -> dict[str, Any]:
    return {
        "decade": decade,
        "actual_age": actual_age,
        "out_of_range": out_of_range.value if out_of_range else None,
    }


def health_age_for_row(row: RiskPrediction, curve: HealthAgeCurve | None) -> dict[str, Any] | None:
    """예측 행 하나의 건강 나이. 모델 행이 아니거나, 곡선이 없거나, 다른 모델 버전의 점수면 null."""
    if row.method != PredictionMethod.MODEL or row.score is None or curve is None:
        return None
    if row.model_version != curve.model_version:
        return None
    inputs = row.input_snapshot.get("inputs", {})
    return estimate_health_age(curve, inputs["sex"], row.score / 100, int(inputs["age"]))
