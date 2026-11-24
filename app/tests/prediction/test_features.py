"""모델 입력 변환 (api.md 5-0 "입력 변환", DB 없이 도는 순수 테스트)."""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.services.prediction import features
from app.services.prediction.features import (
    FEATURE_NAMES,
    SURVEY_INPUT_FIELDS,
    build_input_snapshot,
    calculate_age,
    calculate_bmi,
    is_age_in_range,
    to_feature_vector,
    to_model_inputs,
)


def make_survey(**overrides: Any) -> dict[str, Any]:
    """health_profiles 값 (api.md 3-1 예시: 술 마심·비흡연). 바꿀 값만 overrides로."""
    survey: dict[str, Any] = {
        "height_cm": Decimal("172.5"),
        "weight_kg": Decimal("78.2"),
        "father_diabetes_history": 1,
        "mother_diabetes_history": 0,
        "sibling_diabetes_history": 8,
        "father_hypertension_history": 9,
        "mother_hypertension_history": 1,
        "sibling_hypertension_history": 0,
        "alcohol_frequency": 5,
        "alcohol_amount": 3,
        "smoking_current": 8,
    }
    survey.update(overrides)
    return survey


def test_feature_names_are_12_in_fixed_order() -> None:
    assert len(FEATURE_NAMES) == 12
    assert FEATURE_NAMES[:3] == ("sex", "age", "bmi")
    assert len(SURVEY_INPUT_FIELDS) == 11


def test_model_inputs_follow_rules() -> None:
    model_inputs = to_model_inputs("MALE", 45, make_survey())

    assert list(model_inputs) == list(FEATURE_NAMES)
    assert model_inputs == {
        "sex": 1,
        "age": 45,
        "bmi": 26.3,  # 78.2 / 1.725²
        "father_diabetes_history": 1,
        "mother_diabetes_history": 0,
        "sibling_diabetes_history": 0,  # 형제자매 없음 8 → 0
        "father_hypertension_history": 0,  # 모름 9 → 0
        "mother_hypertension_history": 1,
        "sibling_hypertension_history": 0,
        "alcohol_frequency": 5,
        "alcohol_amount": 3,
        "smoking_current": 0,  # 비해당 8 → 0
    }


def test_knhanes_sex_code_gives_same_result() -> None:
    # 학습은 국건영 원자료(성별 1/2)를 그대로 넣음 → 서버("MALE")와 같은 결과
    assert to_model_inputs(1, 45, make_survey()) == to_model_inputs("MALE", 45, make_survey())
    assert to_model_inputs(2, 45, make_survey())["sex"] == 2


@pytest.mark.parametrize(
    ("alcohol_frequency", "alcohol_amount", "expected"),
    [
        (8, 8, (1, 0)),  # 마셔 본 적 없음 → 빈도 1(전혀), 양 0
        (1, 8, (1, 0)),  # 최근 1년 안 마심
        (6, 5, (6, 5)),
    ],
)
def test_alcohol_rules(alcohol_frequency: int, alcohol_amount: int, expected: tuple[int, int]) -> None:
    survey = make_survey(alcohol_frequency=alcohol_frequency, alcohol_amount=alcohol_amount)

    model_inputs = to_model_inputs("FEMALE", 50, survey)

    assert (model_inputs["alcohol_frequency"], model_inputs["alcohol_amount"]) == expected


@pytest.mark.parametrize(("code", "expected"), [(1, 1), (2, 1), (3, 0), (8, 0)])
def test_smoking_rules(code: int, expected: int) -> None:
    assert to_model_inputs("MALE", 40, make_survey(smoking_current=code))["smoking_current"] == expected


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("father_diabetes_history", 2),
        ("alcohol_frequency", 9),  # 국건영 무응답 9는 학습 전에 걸러야 함
        ("alcohol_amount", 6),
        ("smoking_current", 9),
    ],
)
def test_unknown_code_raises(field: str, code: int) -> None:
    with pytest.raises(ValueError):
        to_model_inputs("MALE", 40, make_survey(**{field: code}))


def test_unknown_sex_raises() -> None:
    with pytest.raises(ValueError):
        to_model_inputs("UNKNOWN", 40, make_survey())
    with pytest.raises(ValueError):
        to_model_inputs(3, 40, make_survey())


def test_bmi_accepts_decimal_and_float() -> None:
    assert calculate_bmi(Decimal("160.0"), Decimal("64.0")) == 25.0
    assert calculate_bmi(160, 64.0) == 25.0
    with pytest.raises(ValueError):
        calculate_bmi(0, 60)


@pytest.mark.parametrize(
    ("birthday", "surveyed_on", "expected"),
    [
        (date(1980, 11, 24), date(2026, 11, 24), 46),  # 생일 당일
        (date(1980, 11, 25), date(2026, 11, 24), 45),  # 생일 하루 전
        (date(1980, 2, 29), date(2026, 2, 28), 45),  # 윤일생은 3/1부터 한 살 더
        (date(1980, 2, 29), date(2026, 3, 1), 46),
    ],
)
def test_calculate_age(birthday: date, surveyed_on: date, expected: int) -> None:
    assert calculate_age(birthday, surveyed_on) == expected


def test_age_range() -> None:
    assert not is_age_in_range(29)
    assert is_age_in_range(30)
    assert is_age_in_range(69)
    assert not is_age_in_range(70)


def test_feature_vector_order() -> None:
    model_inputs = to_model_inputs("MALE", 45, make_survey())

    vector = to_feature_vector(model_inputs)

    assert vector[:3] == [1.0, 45.0, 26.3]
    assert len(vector) == 12


def test_input_snapshot_shape() -> None:
    snapshot = build_input_snapshot("MALE", 45, make_survey())

    # inputs: 설문 11개 + sex(users.gender 그대로)·age, Decimal은 JSON용 float
    assert set(snapshot["inputs"]) == {*SURVEY_INPUT_FIELDS, "sex", "age"}
    assert snapshot["inputs"]["height_cm"] == 172.5
    assert snapshot["inputs"]["sex"] == "MALE"
    assert snapshot["inputs"]["smoking_current"] == 8  # 변환 전 값 그대로
    assert snapshot["model_inputs"]["smoking_current"] == 0


def test_features_module_has_no_app_imports() -> None:
    # 학습 코드(ml/)가 DB 없이 import할 수 있게 표준 라이브러리만 씀
    tree = ast.parse(Path(features.__file__).read_text())
    imported = [
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    ]
    assert not [name for name in imported if name and name.split(".")[0] in {"app", "tortoise", "fastapi"}]
