"""건강 나이·요인 가감 나이 (api.md 5-0 factors, 5-2·5-3 health_age, 11/25 #114 합의).

자가검진 7문항(체중·흡연·음주 빈도·음주량·그 질환 가족력 3개)이 **같은 성별 평균인 사람**보다 위험을 몇 살만큼
올리거나 내리는지 예측 모델 계수로 바꿈. 새로 학습하지 않음.
- 항목 가감 나이 = 계수 × (내 값 − 같은 성별 평균) ÷ 나이 계수
- 건강 나이 = 실제 나이 + clamp(7문항 합(반올림 전), ±15) → 반올림 → 10살 단위 / 30 미만 BELOW / 69 초과 ABOVE
- 요인 = 반올림 전 절댓값 큰 순 → 반올림(부호 대칭) → 0살 빼고 → 3개
- 같은 성별 평균: 모델 JSON의 means_by_sex (장성은). 저장하지 않고 조회 때 input_snapshot으로 계산
DB 없이 쓰는 순수 함수.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Any, Final

from app.core import default_logger as logger
from app.models.risk_predictions import Disease, PredictionMethod, RiskPrediction
from app.services.prediction.features import (
    DIABETES_FAMILY_FIELDS,
    HYPERTENSION_FAMILY_FIELDS,
    MAX_AGE,
    MIN_AGE,
    SEX_CODE_BY_LABEL,
)
from app.services.prediction.model import FACTOR_COUNT, LogisticModel, read_archived_file, read_model_file

HABIT_FIELDS: Final = ("bmi", "smoking_current", "alcohol_frequency", "alcohol_amount")
ITEM_FIELDS_BY_DISEASE: Final[dict[Disease, tuple[str, ...]]] = {
    Disease.DIABETES: (*HABIT_FIELDS, *DIABETES_FAMILY_FIELDS),
    Disease.HYPERTENSION: (*HABIT_FIELDS, *HYPERTENSION_FAMILY_FIELDS),
}
MAX_SHIFT_YEARS: Final = 15


class OutOfRange(StrEnum):
    BELOW = "BELOW"  # 30세 미만 수준
    ABOVE = "ABOVE"  # 69세 초과 수준


@dataclass(frozen=True)
class SexMeans:
    model_version: str  # 이 평균이 들어 있던 모델 JSON의 버전
    means: dict[str, dict[str, float]]  # "MALE"/"FEMALE" → 7문항 평균


@dataclass(frozen=True)
class RowExplanation:
    health_age: dict[str, Any] | None
    factors: list[dict[str, Any]] | None  # None이면 저장된 factors를 years 없이 씀


def parse_means_by_sex(model_version: str, disease: Disease, raw: Mapping[str, Any]) -> SexMeans:
    """JSON의 means_by_sex 검사. 성별 키·7문항이 빠지면 ValueError (CI 모델 파일 테스트가 이걸로 막음)."""
    means: dict[str, dict[str, float]] = {}
    for sex in SEX_CODE_BY_LABEL:
        values = raw.get(sex)
        if not isinstance(values, Mapping):
            raise ValueError(f"means_by_sex에 {sex}가 없음")
        missing = [field for field in ITEM_FIELDS_BY_DISEASE[disease] if field not in values]
        if missing:
            raise ValueError(f"means_by_sex.{sex}에 없는 문항: {missing}")
        means[sex] = {field: float(values[field]) for field in ITEM_FIELDS_BY_DISEASE[disease]}
    return SexMeans(model_version=model_version, means=means)


@cache
def load_sex_means(disease: Disease) -> SexMeans | None:
    """모델 JSON의 means_by_sex. 계수와 따로 읽어서, 어긋나도 예측(점수·단계)은 그대로 나가게 함.

    없으면 None, 어긋나면 에러 로그만 남기고 None → 건강 나이 null, 요인은 저장값(years 없음).
    형식 검사는 CI(모델 파일 테스트)에서 막음.
    """
    try:
        data = read_model_file(disease)
        raw = data.get("means_by_sex")
        if raw is None:
            return None
        return parse_means_by_sex(str(data["model_version"]), disease, raw)
    except (OSError, ValueError, KeyError, TypeError):
        logger.exception("means_by_sex를 읽지 못함 disease=%s", disease.value)
        return None


@cache
def load_archived_sex_means(model_version: str, disease: Disease) -> SexMeans | None:
    """예전 버전 모델 JSON의 means_by_sex. 보관 파일이나 평균이 없으면 None. 형식 오류는 CI에서 막음."""
    data = read_archived_file(model_version)
    raw = data.get("means_by_sex") if data else None
    if raw is None:
        return None
    return parse_means_by_sex(model_version, disease, raw)


def round_half_away(value: float) -> int:
    """부호 대칭 반올림: +2.5 → +3, −2.5 → −3 (to_score의 floor(x + 0.5)는 −2.5 → −2라 안 씀)."""
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def item_years(
    model: LogisticModel, model_inputs: Mapping[str, float], sex_means: Mapping[str, float]
) -> list[tuple[str, float]]:
    """7문항마다 (이름, 가감 나이 반올림 전). 나이 계수가 0 이하면 나이로 바꿀 수 없어서 ValueError."""
    age_coefficient = model.coefficients["age"]
    if age_coefficient <= 0:
        raise ValueError("나이 계수가 0 이하라 가감 나이를 계산할 수 없음")
    return [
        (field, model.coefficients[field] * (float(model_inputs[field]) - sex_means[field]) / age_coefficient)
        for field in ITEM_FIELDS_BY_DISEASE[model.disease]
    ]


def factors_with_years(items: list[tuple[str, float]]) -> list[dict[str, Any]]:
    """반올림 전 절댓값 큰 순 → 반올림 → 0살 빼고 → 3개. 같은 크기면 문항 순서 그대로."""
    ranked = sorted(items, key=lambda item: abs(item[1]), reverse=True)
    factors = []
    for field, raw_years in ranked:
        years = round_half_away(raw_years)
        if years == 0:
            continue
        factors.append({"feature": field, "direction": "UP" if years > 0 else "DOWN", "years": years})
    return factors[:FACTOR_COUNT]


def estimate_health_age(actual_age: int, items: list[tuple[str, float]]) -> dict[str, Any]:
    """실제 나이 + clamp(7문항 합, ±15) → 반올림 → 10살 단위. 학습 범위(30~69) 밖이면 decade 없이 BELOW·ABOVE."""
    shift = max(-MAX_SHIFT_YEARS, min(MAX_SHIFT_YEARS, sum(raw for _, raw in items)))
    health_age = round_half_away(actual_age + shift)
    if health_age < MIN_AGE:
        return health_age_body(None, actual_age, OutOfRange.BELOW)
    if health_age > MAX_AGE:
        return health_age_body(None, actual_age, OutOfRange.ABOVE)
    return health_age_body(health_age // 10 * 10, actual_age, None)


def health_age_body(decade: int | None, actual_age: int, out_of_range: OutOfRange | None) -> dict[str, Any]:
    return {
        "decade": decade,
        "actual_age": actual_age,
        "out_of_range": out_of_range.value if out_of_range else None,
    }


NOT_EXPLAINED: Final = RowExplanation(health_age=None, factors=None)


def explain_row(row: RiskPrediction, model: LogisticModel, sex_means: SexMeans | None) -> RowExplanation:
    """예측 행 하나의 건강 나이 + 요인(가감 나이). 모델 행이 아니거나, 평균이 없거나, 다른 모델 버전이면 둘 다 None."""
    if row.method != PredictionMethod.MODEL or sex_means is None:
        return NOT_EXPLAINED
    if row.model_version != model.model_version or sex_means.model_version != model.model_version:
        return NOT_EXPLAINED
    inputs = row.input_snapshot.get("inputs", {})
    items = item_years(model, row.input_snapshot["model_inputs"], sex_means.means[inputs["sex"]])
    return RowExplanation(
        health_age=estimate_health_age(int(inputs["age"]), items),
        factors=factors_with_years(items),
    )
