"""예측 대상 정하기 (api.md 3-1 응답 managed_diseases·skipped_reason)."""

from app.services.prediction.criteria import Disease
from app.services.prediction.plan import PredictionPlan, SkippedReason, plan_predictions


def plan(**overrides: object) -> PredictionPlan:
    kwargs: dict = {"age": 45, "is_pregnant": None, "is_hypertension_diagnosed": False, "is_diabetes_diagnosed": False}
    kwargs.update(overrides)
    return plan_predictions(**kwargs)


def test_predicts_both_in_order() -> None:
    assert plan() == PredictionPlan(diseases=[Disease.DIABETES, Disease.HYPERTENSION])


def test_diagnosed_disease_is_managed_not_predicted() -> None:
    result = plan(is_hypertension_diagnosed=True)

    assert result.diseases == [Disease.DIABETES]
    assert result.managed_diseases == [Disease.HYPERTENSION]
    assert result.skipped_reason is None


def test_both_diagnosed_predicts_nothing_without_skipped_reason() -> None:
    result = plan(is_hypertension_diagnosed=True, is_diabetes_diagnosed=True)

    assert result.diseases == []
    assert result.managed_diseases == [Disease.DIABETES, Disease.HYPERTENSION]
    assert result.skipped_reason is None


def test_pregnant_skips_all_but_keeps_managed() -> None:
    result = plan(is_pregnant=True, is_diabetes_diagnosed=True)

    assert result.diseases == []
    assert result.managed_diseases == [Disease.DIABETES]
    assert result.skipped_reason == SkippedReason.PREGNANT


def test_not_pregnant_female_predicts() -> None:
    assert plan(is_pregnant=False).diseases == [Disease.DIABETES, Disease.HYPERTENSION]


def test_age_out_of_range() -> None:
    assert plan(age=29).skipped_reason == SkippedReason.AGE_OUT_OF_RANGE
    assert plan(age=70).skipped_reason == SkippedReason.AGE_OUT_OF_RANGE
    assert plan(age=30).skipped_reason is None
    assert plan(age=69).skipped_reason is None


def test_pregnant_reason_wins_over_age() -> None:
    assert plan(age=25, is_pregnant=True).skipped_reason == SkippedReason.PREGNANT
