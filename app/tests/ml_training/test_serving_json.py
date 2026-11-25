"""ml/serving_json.py: 학습 결과 → 서버 JSON·건강 나이 곡선 (가상 데이터만, DB 없이 도는 순수 테스트)."""

import math
from typing import Any

import pytest

from app.models.risk_predictions import Disease
from app.services.prediction.features import FEATURE_NAMES
from app.services.prediction.model import CAUTION_MIN_SCORE, HIGH_MIN_SCORE, LogisticModel, to_score
from ml.serving_json import CURVE_AGES, build_health_age_curve, check_health_age_curve, to_server_json

COEFFICIENTS = dict.fromkeys(FEATURE_NAMES, 0.0) | {"age": 0.05, "bmi": 0.1, "sex": -0.3, "smoking_current": 0.2}
MEANS = dict.fromkeys(FEATURE_NAMES, 0.0) | {"age": 50.0, "bmi": 24.0, "sex": 1.5}


def make_spec(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model_version": "diabetes_risk:test",
        "disease": "DIABETES",
        "intercept": -6.0,
        "coefficients": COEFFICIENTS,
        "means": MEANS,
        "mlflow_run_id": "run-test",
    }
    kwargs.update(overrides)
    return to_server_json(**kwargs)


def make_rows() -> list[dict[str, float]]:
    """가상 사람 8명 (남녀 4명씩, 나이·bmi·흡연만 다르게)."""
    rows = []
    for i in range(8):
        row = dict.fromkeys(FEATURE_NAMES, 0.0)
        row.update(
            {
                "sex": 1.0 if i % 2 == 0 else 2.0,
                "age": 30.0 + 5 * i,
                "bmi": 20.0 + i,
                "smoking_current": float(i % 3 == 0),
            }
        )
        rows.append(row)
    return rows


def make_points(probabilities: list[float]) -> list[dict[str, float]]:
    return [{"age": age, "probability": p} for age, p in zip(CURVE_AGES, probabilities, strict=True)]


def test_server_json_loads_and_matches_server_probability() -> None:
    spec = make_spec()
    model = LogisticModel.from_dict(spec)  # 서버가 읽는 방식 그대로

    assert spec["features"] == list(FEATURE_NAMES)
    assert model.disease == Disease.DIABETES
    assert model.mlflow_run_id == "run-test"
    row = make_rows()[3]
    z = -6.0 + sum(COEFFICIENTS[name] * row[name] for name in FEATURE_NAMES)
    assert model.probability(row) == pytest.approx(1 / (1 + math.exp(-z)))


def test_server_json_rejects_missing_coefficient() -> None:
    without_bmi = {name: value for name, value in COEFFICIENTS.items() if name != "bmi"}
    with pytest.raises(ValueError):
        make_spec(coefficients=without_bmi)


def test_curve_is_mean_probability_with_only_age_changed() -> None:
    # 같은 성별 전원의 나이만 바꿔 서버 모델로 계산한 확률 평균과 같아야 함 (11/24 검증 방식)
    spec = make_spec()
    model = LogisticModel.from_dict(spec)
    rows = make_rows()

    curve = build_health_age_curve(spec, rows)

    for label, code in (("MALE", 1.0), ("FEMALE", 2.0)):
        group = [row for row in rows if row["sex"] == code]
        assert [point["age"] for point in curve[label]] == list(CURVE_AGES)
        for point in curve[label]:
            expected = sum(model.probability(row | {"age": point["age"]}) for row in group) / len(group)
            assert point["probability"] == pytest.approx(expected)


def test_curve_needs_positive_age_coefficient_and_both_sexes() -> None:
    with pytest.raises(ValueError):
        build_health_age_curve(make_spec(coefficients=COEFFICIENTS | {"age": -0.01}), make_rows())
    with pytest.raises(ValueError):
        build_health_age_curve(make_spec(), [row for row in make_rows() if row["sex"] == 1.0])


@pytest.mark.parametrize(
    "broken",
    [
        {"FEMALE": None},  # 성별 빠짐
        {"MALE": make_points([0.01 * (i + 1) for i in range(40)])[:-1]},  # 39개
        {"MALE": make_points([0.01 * (i + 1) for i in range(39)] + [1.2])},  # 0~1 밖
        {"MALE": make_points([0.01 * (i + 1) for i in range(39)] + [0.39])},  # 마지막이 앞과 같음
    ],
)
def test_check_curve_rejects_broken(broken: dict[str, Any]) -> None:
    good = make_points([0.01 * (i + 1) for i in range(40)])
    curve: dict[str, Any] = {"MALE": good, "FEMALE": good} | broken
    with pytest.raises(ValueError):
        check_health_age_curve(curve)


def test_evaluate_score_rules_match_server() -> None:
    # ml/evaluate.py는 numpy·sklearn이 필요해서 ml 그룹이 있는 PC에서만 돎 (CI는 건너뜀)
    np = pytest.importorskip("numpy")
    evaluate = pytest.importorskip("ml.evaluate")

    probabilities = [0.0, 0.2949, 0.295, 0.345, 0.596, 0.995, 1.0]
    assert list(evaluate.to_score(np.array(probabilities))) == [to_score(p) for p in probabilities]
    assert (evaluate.CAUTION_MIN_SCORE, evaluate.HIGH_MIN_SCORE) == (CAUTION_MIN_SCORE, HIGH_MIN_SCORE)
