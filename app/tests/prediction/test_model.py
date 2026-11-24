"""모델 JSON 추론·점수·단계·factors (api.md 5-0, DB 없이 도는 순수 테스트)."""

import math
from typing import Any

import pytest

from app.models.risk_predictions import Disease, RiskLevel
from app.services.prediction.features import FEATURE_NAMES
from app.services.prediction.model import LogisticModel, load_model, to_level, to_score


def make_model_dict(**overrides: Any) -> dict[str, Any]:
    coefficients = dict.fromkeys(FEATURE_NAMES, 0.0)
    coefficients.update({"bmi": 0.1, "age": 0.05, "sex": 0.3, "father_hypertension_history": 0.4})
    data: dict[str, Any] = {
        "model_version": "diabetes_risk:test",
        "disease": "DIABETES",
        "features": list(FEATURE_NAMES),
        "intercept": -6.0,
        "coefficients": coefficients,
        "means": dict.fromkeys(FEATURE_NAMES, 0.0) | {"bmi": 24.0, "age": 50.0, "sex": 1.5},
    }
    data.update(overrides)
    return data


def make_inputs(**overrides: float) -> dict[str, float]:
    inputs = dict.fromkeys(FEATURE_NAMES, 0.0) | {"sex": 1.0, "age": 50.0, "bmi": 30.0}
    inputs.update(overrides)
    return inputs


def test_probability_is_logistic_of_linear_sum() -> None:
    model = LogisticModel.from_dict(make_model_dict())

    # -6 + 0.05·50 + 0.1·30 + 0.3·1 = -0.2
    assert model.probability(make_inputs()) == pytest.approx(1 / (1 + math.exp(0.2)))


def test_features_must_match_feature_names() -> None:
    reordered = list(reversed(FEATURE_NAMES))
    with pytest.raises(ValueError):
        LogisticModel.from_dict(make_model_dict(features=reordered))


@pytest.mark.parametrize(("probability", "score"), [(0.0, 0), (0.345, 35), (0.2949, 29), (0.995, 100), (1.0, 100)])
def test_to_score_rounds_half_up(probability: float, score: int) -> None:
    assert to_score(probability) == score


@pytest.mark.parametrize(
    ("score", "level"),
    [(0, RiskLevel.LOW), (29, RiskLevel.LOW), (30, RiskLevel.CAUTION), (59, RiskLevel.CAUTION), (60, RiskLevel.HIGH)],
)
def test_to_level_uses_30_and_60(score: int, level: RiskLevel) -> None:
    assert to_level(score) == level


def test_level_follows_rounded_score() -> None:
    # 확률 0.596 → score 60 → HIGH (확률로 비교하면 CAUTION이라 화면 숫자와 어긋남)
    assert to_level(to_score(0.596)) == RiskLevel.HIGH


def test_factors_top3_by_contribution_excluding_sex_and_other_family() -> None:
    model = LogisticModel.from_dict(make_model_dict())
    inputs = make_inputs(bmi=30.0, age=60.0, father_hypertension_history=1.0, sex=2.0)

    factors = model.factors(inputs)

    # bmi 0.1×6=0.6, age 0.05×10=0.5 / sex(0.15)·고혈압 가족력(0.4)은 당뇨 factors 후보에서 뺌
    assert factors == [{"feature": "bmi", "direction": "UP"}, {"feature": "age", "direction": "UP"}]


def test_factors_direction_down() -> None:
    model = LogisticModel.from_dict(make_model_dict())

    factors = model.factors(make_inputs(bmi=20.0))

    assert factors[0] == {"feature": "bmi", "direction": "DOWN"}


def test_model_files_load_for_each_disease() -> None:
    # model_files/의 JSON(가짜든 진짜든)이 형식에 맞는지만 봄. 점수는 파일마다 달라서 API 테스트는 fixed_model을 씀
    for disease in Disease:
        model = load_model(disease)

        assert model.disease == disease
        assert model.model_version.startswith(f"{disease.lower()}_risk:")
        assert 0 < model.probability(make_inputs()) < 1
