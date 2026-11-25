"""건강 나이 곡선 검사·계산 (api.md 5-2·5-3, DB 없이 도는 순수 테스트)."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.models.risk_predictions import Disease, PredictionMethod, RiskLevel, RiskPrediction
from app.services.prediction import model as model_module
from app.services.prediction.health_age import (
    estimate_health_age,
    health_age_for_row,
    parse_health_age_curve,
)
from app.tests.prediction.fixed_models import make_curve_points

VERSION = "diabetes_risk:v1"


def curve_dict(**overrides: Any) -> dict[str, Any]:
    points = make_curve_points()
    data: dict[str, Any] = {"MALE": points, "FEMALE": points}
    data.update(overrides)
    return data


def test_parse_accepts_valid_curve() -> None:
    curve = parse_health_age_curve(VERSION, curve_dict())

    assert curve.model_version == VERSION
    assert len(curve.probabilities_by_sex["MALE"]) == 40


@pytest.mark.parametrize(
    "broken",
    [
        {"FEMALE": None},  # 성별 빠짐
        {"MALE": make_curve_points()[:-1]},  # 39개
        {"MALE": [{"age": age + 1, "probability": 0.01 * (age - 28)} for age in range(30, 70)]},  # 31~70세
        {"MALE": [*make_curve_points()[:-1], {"age": 69, "probability": 1.2}]},  # 0~1 밖
        {"MALE": [*make_curve_points()[:-1], {"age": 69, "probability": 0.39}]},  # 마지막이 앞과 같음
    ],
)
def test_parse_rejects_broken_curve(broken: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_health_age_curve(VERSION, curve_dict(**broken))


@pytest.mark.parametrize(
    ("probability", "decade", "out_of_range"),
    [
        (0.155, 40, None),  # 44.5세 → 40대
        (0.10, 30, None),  # 39.0세 → 30대
        (0.11, 40, None),  # 40.0세 → 40대 (경계)
        (0.01, 30, None),  # 곡선 처음 = 30세
        (0.40, 60, None),  # 곡선 끝 = 69세 → 60대
        (0.005, None, "BELOW"),  # 30세 이하 수준
        (0.41, None, "ABOVE"),  # 69세 이상 수준
    ],
)
def test_estimate(probability: float, decade: int | None, out_of_range: str | None) -> None:
    curve = parse_health_age_curve(VERSION, curve_dict())

    result = estimate_health_age(curve, "MALE", probability, actual_age=45)

    assert result == {"decade": decade, "actual_age": 45, "out_of_range": out_of_range}


def test_estimate_uses_own_sex_curve() -> None:
    female = [{"age": age, "probability": round(0.005 * (age - 29), 4)} for age in range(30, 70)]
    curve = parse_health_age_curve(VERSION, curve_dict(FEMALE=female))

    # 같은 확률 0.10: 남성 곡선 39세 → 30대, 여성 곡선 49세 → 40대
    assert estimate_health_age(curve, "MALE", 0.10, 45)["decade"] == 30
    assert estimate_health_age(curve, "FEMALE", 0.10, 45)["decade"] == 40


def make_row(**overrides: Any) -> RiskPrediction:
    values: dict[str, Any] = {
        "id": 1,
        "user_id": 1,
        "health_profile_id": 1,
        "disease": Disease.DIABETES,
        "method": PredictionMethod.MODEL,
        "score": 34,
        "level": RiskLevel.CAUTION,
        "model_version": VERSION,
        "input_snapshot": {"inputs": {"sex": "MALE", "age": 45}},
        "created_at": datetime(2026, 11, 25, tzinfo=UTC),
    }
    values.update(overrides)
    return RiskPrediction(**values)


def test_row_uses_score_over_100_and_snapshot_age() -> None:
    curve = parse_health_age_curve(VERSION, curve_dict())

    # score 34 → 확률 0.34 → 63세 → 60대, 실제 나이는 예측 때 나이(input_snapshot)
    assert health_age_for_row(make_row(), curve) == {"decade": 60, "actual_age": 45, "out_of_range": None}


def test_row_without_curve_or_other_version_is_null() -> None:
    curve = parse_health_age_curve(VERSION, curve_dict())

    assert health_age_for_row(make_row(), None) is None
    # 가짜 모델로 저장된 예전 점수에 진짜 모델 곡선을 섞지 않음
    assert health_age_for_row(make_row(model_version="diabetes_risk:dummy"), curve) is None


def test_criteria_row_is_null() -> None:
    curve = parse_health_age_curve(VERSION, curve_dict())
    criteria = make_row(method=PredictionMethod.CHECKUP_CRITERIA, score=None, model_version=None)

    assert health_age_for_row(criteria, curve) is None


def test_broken_curve_file_logs_and_returns_none() -> None:
    # 실행 중 곡선이 어긋나도 예측은 그대로, 건강 나이만 null (팀장님 의견 11/25)
    broken = {"model_version": VERSION, "health_age_curve": curve_dict(MALE=make_curve_points()[:10])}
    model_module.load_health_age_curve.cache_clear()
    try:
        with patch.object(model_module, "read_model_file", return_value=broken):
            assert model_module.load_health_age_curve(Disease.DIABETES) is None
    finally:
        model_module.load_health_age_curve.cache_clear()
