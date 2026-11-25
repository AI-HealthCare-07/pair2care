"""건강 나이·요인 가감 나이 (api.md 5-0·5-2·5-3, #114). DB 없이 도는 순수 테스트."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.models.risk_predictions import Disease, PredictionMethod, RiskLevel, RiskPrediction
from app.services.prediction import health_age as health_age_module
from app.services.prediction.features import FEATURE_NAMES
from app.services.prediction.health_age import (
    ITEM_FIELDS_BY_DISEASE,
    SexMeans,
    estimate_health_age,
    explain_row,
    factors_with_years,
    item_years,
    parse_means_by_sex,
    round_half_away,
)
from app.services.prediction.model import LogisticModel

VERSION = "diabetes_risk:test"
DIABETES_ITEMS = ITEM_FIELDS_BY_DISEASE[Disease.DIABETES]


def make_model(**coefficients: float) -> LogisticModel:
    """나이 계수 0.05 → 계수 0.1인 항목은 1단위에 2살."""
    values = dict.fromkeys(FEATURE_NAMES, 0.0) | {"age": 0.05} | coefficients
    return LogisticModel(
        model_version=VERSION,
        disease=Disease.DIABETES,
        intercept=-5.0,
        coefficients=values,
        means=dict.fromkeys(FEATURE_NAMES, 0.0),
    )


def sex_means(**overrides: float) -> dict[str, float]:
    return dict.fromkeys(DIABETES_ITEMS, 0.0) | {"bmi": 24.0} | overrides


def make_inputs(**overrides: float) -> dict[str, float]:
    return dict.fromkeys(FEATURE_NAMES, 0.0) | {"sex": 1.0, "age": 45.0, "bmi": 24.0} | overrides


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
        "input_snapshot": {"inputs": {"sex": "MALE", "age": 45}, "model_inputs": make_inputs(bmi=26.5)},
        "created_at": datetime(2026, 11, 25, tzinfo=UTC),
    }
    values.update(overrides)
    return RiskPrediction(**values)


def both_sexes(**overrides: float) -> SexMeans:
    return SexMeans(model_version=VERSION, means={"MALE": sex_means(**overrides), "FEMALE": sex_means(bmi=22.0)})


# ───── 반올림·정렬 ─────
@pytest.mark.parametrize(
    ("value", "expected"),
    [(2.5, 3), (-2.5, -3), (2.4, 2), (-2.4, -2), (0.49, 0), (-0.49, 0), (0.0, 0)],
)
def test_round_half_away_is_symmetric(value: float, expected: int) -> None:
    assert round_half_away(value) == expected


def test_factors_sort_before_rounding_drop_zero_and_keep_three() -> None:
    items = [("bmi", 2.4), ("smoking_current", -2.6), ("alcohol_frequency", 0.3), ("alcohol_amount", 2.45), ("x", 5.0)]

    factors = factors_with_years(items)

    # 반올림 전 크기 순: 5.0 → −2.6 → 2.45 → 2.4 (반올림하면 셋 다 2~3살이라 반올림 후 정렬이면 순서가 흔들림)
    assert factors == [
        {"feature": "x", "direction": "UP", "years": 5},
        {"feature": "smoking_current", "direction": "DOWN", "years": -3},
        {"feature": "alcohol_amount", "direction": "UP", "years": 2},
    ]


def test_factors_skip_items_that_round_to_zero() -> None:
    assert factors_with_years([("bmi", 0.4), ("smoking_current", -0.2)]) == []


# ───── 가감 나이 ─────
def test_item_years_use_same_sex_mean_and_age_coefficient() -> None:
    model = make_model(bmi=0.1, smoking_current=0.2)
    items = dict(item_years(model, make_inputs(bmi=26.0, smoking_current=1.0), sex_means(smoking_current=0.5)))

    assert items["bmi"] == pytest.approx(4.0)  # 0.1 × (26 − 24) ÷ 0.05
    assert items["smoking_current"] == pytest.approx(2.0)  # 0.2 × (1 − 0.5) ÷ 0.05
    assert set(items) == set(DIABETES_ITEMS)  # 다른 질환 가족력·성별·나이는 안 들어감


def test_item_years_need_positive_age_coefficient() -> None:
    with pytest.raises(ValueError, match="나이 계수"):
        item_years(make_model(age=0.0), make_inputs(), sex_means())


# ───── 건강 나이 ─────
def test_health_age_adds_items_and_shows_decade() -> None:
    assert estimate_health_age(45, [("bmi", 4.0), ("smoking_current", 2.0)]) == {
        "decade": 50,
        "actual_age": 45,
        "out_of_range": None,
    }


def test_health_age_shift_is_clamped_to_15() -> None:
    assert estimate_health_age(45, [("bmi", 12.0), ("x", 10.0)])["decade"] == 60  # 45 + 15 = 60
    assert estimate_health_age(45, [("bmi", -40.0)])["decade"] == 30  # 45 − 15 = 30, BELOW 아님


def test_health_age_out_of_range() -> None:
    assert estimate_health_age(38, [("bmi", -20.0)])["out_of_range"] == "BELOW"  # 38 − 15 = 23
    assert estimate_health_age(60, [("bmi", 10.0)])["out_of_range"] == "ABOVE"  # 70
    assert estimate_health_age(60, [("bmi", 9.4)])["decade"] == 60  # 69.4 → 69, 아직 범위 안
    assert estimate_health_age(30, [("bmi", -0.6)])["out_of_range"] == "BELOW"  # 29.4 → 29


# ───── 행 하나 ─────
def test_explain_row_gives_health_age_and_factors_with_same_basis() -> None:
    explanation = explain_row(make_row(), make_model(bmi=0.1), both_sexes())

    # 남성 평균 24 → bmi 26.5는 +5살 → 50대
    assert explanation.factors == [{"feature": "bmi", "direction": "UP", "years": 5}]
    assert explanation.health_age == {"decade": 50, "actual_age": 45, "out_of_range": None}


def test_explain_row_uses_own_sex_mean() -> None:
    female = make_row(input_snapshot={"inputs": {"sex": "FEMALE", "age": 45}, "model_inputs": make_inputs(bmi=26.5)})

    assert explain_row(female, make_model(bmi=0.1), both_sexes()).factors == [
        {"feature": "bmi", "direction": "UP", "years": 9}  # 여성 평균 22 → 0.1 × 4.5 ÷ 0.05
    ]


@pytest.mark.parametrize(
    "row_overrides",
    [
        {"method": PredictionMethod.CHECKUP_CRITERIA, "score": None},
        {"model_version": "diabetes_risk:old"},
    ],
)
def test_explain_row_none_for_criteria_or_other_version(row_overrides: dict[str, Any]) -> None:
    explanation = explain_row(make_row(**row_overrides), make_model(bmi=0.1), both_sexes())

    assert explanation.health_age is None and explanation.factors is None


def test_explain_row_none_without_sex_means() -> None:
    explanation = explain_row(make_row(), make_model(bmi=0.1), None)

    assert explanation.health_age is None and explanation.factors is None


# ───── JSON 읽기 ─────
def test_parse_means_by_sex() -> None:
    parsed = parse_means_by_sex(VERSION, Disease.DIABETES, {"MALE": sex_means(), "FEMALE": sex_means(bmi=22.0)})

    assert parsed.model_version == VERSION
    assert parsed.means["FEMALE"]["bmi"] == 22.0


@pytest.mark.parametrize(
    "raw",
    [
        {"MALE": sex_means()},  # FEMALE 없음
        {"MALE": sex_means(), "FEMALE": {"bmi": 22.0}},  # 7문항 중 빠짐
    ],
)
def test_parse_means_by_sex_rejects_broken(raw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_means_by_sex(VERSION, Disease.DIABETES, raw)


def test_broken_means_file_logs_and_returns_none() -> None:
    broken = {"model_version": VERSION, "means_by_sex": {"MALE": sex_means()}}
    health_age_module.load_sex_means.cache_clear()
    try:
        with patch.object(health_age_module, "read_model_file", return_value=broken):
            assert health_age_module.load_sex_means(Disease.DIABETES) is None
    finally:
        health_age_module.load_sex_means.cache_clear()
