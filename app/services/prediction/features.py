"""예측 모델 입력 변환 — 학습(ml/)과 서빙(app/)이 같이 쓰는 한 곳 (api.md 5-0 "입력 변환", 11/23 확정).

학습 전처리와 서빙이 각자 변환을 짜면 어긋나므로 이 파일 하나만 쓴다.
ml/ 학습 코드에서도 import하므로 표준 라이브러리만 쓰고 app의 DB 모델(Tortoise)은 import하지 않는다.

입력은 국건영 코드 그대로 (survey-mapping.md). 서버는 health_profiles 값을, 학습은 국건영 원자료 값을 넣으면 됨.
- 성별: 서버 "MALE" / "FEMALE", 국건영 1 / 2 둘 다 받음
- 모르는 코드가 오면 ValueError (학습 데이터의 무응답 9 등을 조용히 바꾸지 않고 드러냄)
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any, Final

Number = int | float | Decimal

# 학습 범위 (variables.md 1-1). 밖이면 예측 대신 일반 안내
MIN_AGE: Final = 30
MAX_AGE: Final = 69

FAMILY_HISTORY_FIELDS: Final = (
    "father_diabetes_history",
    "mother_diabetes_history",
    "sibling_diabetes_history",
    "father_hypertension_history",
    "mother_hypertension_history",
    "sibling_hypertension_history",
)
DIABETES_FAMILY_FIELDS: Final = FAMILY_HISTORY_FIELDS[:3]
HYPERTENSION_FAMILY_FIELDS: Final = FAMILY_HISTORY_FIELDS[3:]

# 변환 전 설문 값 11개 (input_snapshot.inputs, changed_inputs 비교 대상)
SURVEY_INPUT_FIELDS: Final = (
    "height_cm",
    "weight_kg",
    *FAMILY_HISTORY_FIELDS,
    "alcohol_frequency",
    "alcohol_amount",
    "smoking_current",
)

# 모델 입력 12개. 순서 고정 = 모델 JSON features 순서 (계수와 같은 순서)
FEATURE_NAMES: Final = (
    "sex",
    "age",
    "bmi",
    *FAMILY_HISTORY_FIELDS,
    "alcohol_frequency",
    "alcohol_amount",
    "smoking_current",
)

SEX_CODE_BY_LABEL: Final[dict[str, int]] = {"MALE": 1, "FEMALE": 2}
FAMILY_HISTORY_CODES: Final = frozenset({0, 1, 8, 9})  # 아니요 0 / 예 1 / 형제자매 없음 8 / 모름 9
ALCOHOL_FREQUENCY_CODES: Final = frozenset({1, 2, 3, 4, 5, 6, 8})
ALCOHOL_AMOUNT_CODES: Final = frozenset({1, 2, 3, 4, 5, 8})
SMOKING_CURRENT_CODES: Final = frozenset({1, 2, 3, 8})
NOT_APPLICABLE: Final = 8


def calculate_age(birthday: date, surveyed_on: date) -> int:
    """설문 날짜(KST) 기준 만 나이."""
    had_birthday = (surveyed_on.month, surveyed_on.day) >= (birthday.month, birthday.day)
    return surveyed_on.year - birthday.year - (0 if had_birthday else 1)


def is_age_in_range(age: int) -> bool:
    return MIN_AGE <= age <= MAX_AGE


def to_sex_code(sex: str | int) -> int:
    """ "MALE"/"FEMALE" 또는 국건영 1/2 → 1 남 / 2 여."""
    if isinstance(sex, str):
        if sex not in SEX_CODE_BY_LABEL:
            raise ValueError(f"알 수 없는 성별: {sex!r}")
        return SEX_CODE_BY_LABEL[sex]
    if sex not in (1, 2):
        raise ValueError(f"알 수 없는 성별 코드: {sex!r}")
    return sex


def calculate_bmi(height_cm: Number, weight_kg: Number) -> float:
    """몸무게 ÷ (키/100)², 소수 첫째 자리 (키·몸무게는 모델에 따로 넣지 않음)."""
    height_m = float(height_cm) / 100
    if height_m <= 0:
        raise ValueError(f"키가 0 이하: {height_cm!r}")
    return round(float(weight_kg) / (height_m * height_m), 1)


def to_family_history_flag(code: int) -> int:
    """예(1)만 1, 아니요·모름·형제자매 없음(0·9·8)은 0."""
    check_code("가족력", code, FAMILY_HISTORY_CODES)
    return 1 if code == 1 else 0


def to_alcohol_frequency(code: int) -> int:
    """비해당 8(마셔 본 적 없음) → 1(전혀), 나머지 1~6 그대로."""
    check_code("alcohol_frequency", code, ALCOHOL_FREQUENCY_CODES)
    return 1 if code == NOT_APPLICABLE else code


def to_alcohol_amount(code: int) -> int:
    """비해당 8(최근 1년 안 마심) → 0, 나머지 1~5 그대로."""
    check_code("alcohol_amount", code, ALCOHOL_AMOUNT_CODES)
    return 0 if code == NOT_APPLICABLE else code


def to_smoking_flag(code: int) -> int:
    """매일·가끔(1·2) → 1, 지금은 안 피움·피운 적 없음(3·8) → 0."""
    check_code("smoking_current", code, SMOKING_CURRENT_CODES)
    return 1 if code in (1, 2) else 0


def check_code(name: str, code: int, allowed: frozenset[int]) -> None:
    if code not in allowed:
        raise ValueError(f"{name}에 알 수 없는 코드: {code!r} (허용 {sorted(allowed)})")


def to_model_inputs(sex: str | int, age: int, survey: Mapping[str, Any]) -> dict[str, int | float]:
    """설문 값 11개 + 성별·나이 → 모델 입력 12개 (FEATURE_NAMES 순서)."""
    model_inputs: dict[str, int | float] = {
        "sex": to_sex_code(sex),
        "age": age,
        "bmi": calculate_bmi(survey["height_cm"], survey["weight_kg"]),
    }
    for field in FAMILY_HISTORY_FIELDS:
        model_inputs[field] = to_family_history_flag(int(survey[field]))
    model_inputs["alcohol_frequency"] = to_alcohol_frequency(int(survey["alcohol_frequency"]))
    model_inputs["alcohol_amount"] = to_alcohol_amount(int(survey["alcohol_amount"]))
    model_inputs["smoking_current"] = to_smoking_flag(int(survey["smoking_current"]))
    return model_inputs


def to_feature_vector(model_inputs: Mapping[str, int | float]) -> list[float]:
    """모델 입력 dict → 계수와 곱할 순서의 숫자 목록 (학습 X 행과 같은 순서)."""
    return [float(model_inputs[name]) for name in FEATURE_NAMES]


def build_input_snapshot(sex: str, age: int, survey: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """risk_predictions.input_snapshot (api.md 5-0): 변환 전 inputs + 변환 후 model_inputs."""
    inputs: dict[str, Any] = {field: to_json_number(survey[field]) for field in SURVEY_INPUT_FIELDS}
    inputs["sex"] = sex
    inputs["age"] = age
    return {"inputs": inputs, "model_inputs": to_model_inputs(sex, age, survey)}


def to_json_number(value: Any) -> Any:
    """DB의 Decimal(키·몸무게)을 JSON에 넣을 수 있게 float로."""
    return float(value) if isinstance(value, Decimal) else value
