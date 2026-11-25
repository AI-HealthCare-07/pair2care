"""ml/serving_json.py: 학습 결과 → 서버 JSON·같은 성별 평균 (가상 데이터만, DB 없이 도는 순수 테스트)."""

import math
from typing import Any

import pytest

from app.models.risk_predictions import Disease
from app.services.prediction.features import FEATURE_NAMES
from app.services.prediction.health_age import ITEM_FIELDS_BY_DISEASE, parse_means_by_sex
from app.services.prediction.model import CAUTION_MIN_SCORE, HIGH_MIN_SCORE, LogisticModel, to_score
from ml.serving_json import build_means_by_sex, health_age_fields, to_server_json

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


@pytest.mark.parametrize("disease", list(Disease))
def test_health_age_fields_are_server_items_in_feature_order(disease: Disease) -> None:
    fields = health_age_fields(disease)

    assert set(fields) == set(ITEM_FIELDS_BY_DISEASE[disease])  # 서버 7문항과 같은 목록 (학습·서빙 어긋남 방지)
    assert list(fields) == [name for name in FEATURE_NAMES if name in fields]  # JSON 순서는 FEATURE_NAMES


def test_means_by_sex_is_mean_within_each_sex_and_server_reads_it() -> None:
    rows = make_rows()
    fields = health_age_fields(Disease.DIABETES)

    means_by_sex = build_means_by_sex(rows, fields)

    for label, code in (("MALE", 1.0), ("FEMALE", 2.0)):
        group = [row for row in rows if row["sex"] == code]
        assert list(means_by_sex[label]) == list(fields)
        for name in fields:
            assert means_by_sex[label][name] == pytest.approx(sum(row[name] for row in group) / len(group))
    # 서버가 읽는 방식 그대로 (성별 2개 × 7문항 검사)
    parse_means_by_sex("diabetes_risk:test", Disease.DIABETES, means_by_sex)


def test_means_by_sex_needs_both_sexes() -> None:
    with pytest.raises(ValueError):
        build_means_by_sex([row for row in make_rows() if row["sex"] == 1.0], health_age_fields(Disease.DIABETES))


def test_evaluate_score_rules_match_server() -> None:
    # ml/evaluate.py는 numpy·sklearn이 필요해서 ml 그룹이 있는 PC에서만 돎 (CI는 건너뜀)
    np = pytest.importorskip("numpy")
    evaluate = pytest.importorskip("ml.evaluate")

    probabilities = [0.0, 0.2949, 0.295, 0.345, 0.596, 0.995, 1.0]
    assert list(evaluate.to_score(np.array(probabilities))) == [to_score(p) for p in probabilities]
    assert (evaluate.CAUTION_MIN_SCORE, evaluate.HIGH_MIN_SCORE) == (CAUTION_MIN_SCORE, HIGH_MIN_SCORE)
