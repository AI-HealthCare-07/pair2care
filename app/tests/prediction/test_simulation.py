"""5-4 습관 시뮬레이션 규칙 (DB 없이 도는 순수 테스트)."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException

from app.services.prediction.simulation import SimulationChanges, apply_changes, check_simulatable_keys
from app.tests.survey.test_validation import make_answers

# 가입 설문 저장 결과: 술 마심(빈도 5·양 3), 담배 피운 적 없음
SAVED_SURVEY: dict[str, Any] = make_answers(smoking_current=8, cigarettes_per_day=888)


def changes(**values: Any) -> SimulationChanges:
    return SimulationChanges.model_validate(values)


def test_other_fields_are_400() -> None:
    with pytest.raises(HTTPException) as exc:
        check_simulatable_keys({"weight_kg": 75.0, "height_cm": 180.0})
    assert exc.value.status_code == 400
    assert exc.value.detail == "체중·음주·흡연만 바꿔 볼 수 있어요."


def test_empty_changes_are_400() -> None:
    with pytest.raises(HTTPException):
        check_simulatable_keys({})


def test_weight_change_overrides_only_weight() -> None:
    merged = apply_changes(SAVED_SURVEY, changes(weight_kg=75.0))

    assert merged["weight_kg"] == Decimal("75.0")
    assert merged["alcohol_frequency"] == 5
    assert merged["height_cm"] == SAVED_SURVEY["height_cm"]


def test_stop_drinking_fills_amount_8() -> None:
    merged = apply_changes(SAVED_SURVEY, changes(alcohol_frequency=1))

    assert (merged["alcohol_frequency"], merged["alcohol_amount"]) == (1, 8)


def test_stop_drinking_with_amount_is_400() -> None:
    with pytest.raises(HTTPException) as exc:
        apply_changes(SAVED_SURVEY, changes(alcohol_frequency=1, alcohol_amount=2))
    assert exc.value.detail == "최근 1년간 술을 마시지 않았다면 한 번 음주량은 보낼 수 없어요."


def test_start_drinking_again_needs_amount() -> None:
    not_drinking_lately = {**SAVED_SURVEY, "alcohol_frequency": 1, "alcohol_amount": 8}

    with pytest.raises(HTTPException) as exc:
        apply_changes(not_drinking_lately, changes(alcohol_frequency=3))
    assert exc.value.detail == "한 번에 마시는 양을 골라 주세요."

    merged = apply_changes(not_drinking_lately, changes(alcohol_frequency=3, alcohol_amount=1))
    assert (merged["alcohol_frequency"], merged["alcohol_amount"]) == (3, 1)


@pytest.mark.parametrize(
    ("survey", "values"),
    [
        ({**SAVED_SURVEY, "alcohol_ever": 1}, {"alcohol_frequency": 3}),  # 술을 마셔 본 적 없음
        ({**SAVED_SURVEY, "alcohol_ever": 1}, {"alcohol_amount": 2}),
        (SAVED_SURVEY, {"smoking_current": 3}),  # 담배를 피운 적 없음
    ],
)
def test_not_applicable_habit_is_400(survey: dict[str, Any], values: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as exc:
        apply_changes(survey, changes(**values))
    assert exc.value.detail == "지금 해당하지 않는 습관은 바꿔 볼 수 없어요."


def test_quit_smoking_for_smoker() -> None:
    smoker = {**SAVED_SURVEY, "smoking_lifetime": 2, "smoking_current": 1, "cigarettes_per_day": 10}

    assert apply_changes(smoker, changes(smoking_current=3))["smoking_current"] == 3
