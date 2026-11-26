"""설문 문항 정의 — 3-1 검사와 3-6 응답이 함께 보는 서버 상수 (api.md 3-1·3-6, 11/23 7번 결정).

- 문구·보기·저장값·건너뛰기 조건: 장성은 초안 (survey_questions_v1.0.json, survey-mapping.md 기준)
- 문항이나 코드가 바뀌면 survey-mapping.md와 이 파일을 같은 PR에서 고치고 SURVEY_VERSION을 올림
- ONBOARDING 21문항 하나만 두고 WEEKLY는 여기서 걸러 냄 (문구를 두 군데 두지 않음)
"""

import copy
from typing import Any, Final

from app.models.health_profiles import SurveyKind

SURVEY_VERSION: Final = "v1.0"

# 3-6 ONBOARDING 응답의 questions 그대로. 배열 순서 = 화면 순서, options 순서 = 보기 순서
QUESTIONS: Final[list[dict[str, Any]]] = [
    {
        "no": 1,
        "field": "height_cm",
        "text": "키를 알려 주세요.",
        "type": "NUMBER",
        "min": 100.0,
        "max": 230.0,
        "step": 0.1,
        "unit": "cm",
        "required": True,
    },
    {
        "no": 2,
        "field": "weight_kg",
        "text": "몸무게를 알려 주세요.",
        "type": "NUMBER",
        "min": 25.0,
        "max": 300.0,
        "step": 0.1,
        "unit": "kg",
        "required": True,
    },
    {
        "no": 3,
        "field": "waist_cm",
        "text": "허리둘레를 알려 주세요.",
        "type": "NUMBER",
        "min": 40.0,
        "max": 200.0,
        "step": 0.1,
        "unit": "cm",
        "required": False,
    },
    {
        "no": 4,
        "field": "father_diabetes_history",
        "text": "아버지가 당뇨 진단을 받았나요?",
        "type": "SINGLE",
        "options": [{"label": "예", "value": 1}, {"label": "아니요", "value": 0}, {"label": "모름", "value": 9}],
    },
    {
        "no": 5,
        "field": "mother_diabetes_history",
        "text": "어머니가 당뇨 진단을 받았나요?",
        "type": "SINGLE",
        "options": [{"label": "예", "value": 1}, {"label": "아니요", "value": 0}, {"label": "모름", "value": 9}],
    },
    {
        "no": 6,
        "field": "sibling_diabetes_history",
        "text": "형제자매 중 당뇨 진단을 받은 사람이 있나요?",
        "type": "SINGLE",
        "options": [
            {"label": "예", "value": 1},
            {"label": "아니요", "value": 0},
            {"label": "모름", "value": 9},
            {"label": "형제자매 없음", "value": 8},
        ],
    },
    {
        "no": 7,
        "field": "father_hypertension_history",
        "text": "아버지가 고혈압 진단을 받았나요?",
        "type": "SINGLE",
        "options": [{"label": "예", "value": 1}, {"label": "아니요", "value": 0}, {"label": "모름", "value": 9}],
    },
    {
        "no": 8,
        "field": "mother_hypertension_history",
        "text": "어머니가 고혈압 진단을 받았나요?",
        "type": "SINGLE",
        "options": [{"label": "예", "value": 1}, {"label": "아니요", "value": 0}, {"label": "모름", "value": 9}],
    },
    {
        "no": 9,
        "field": "sibling_hypertension_history",
        "text": "형제자매 중 고혈압 진단을 받은 사람이 있나요?",
        "type": "SINGLE",
        "options": [
            {"label": "예", "value": 1},
            {"label": "아니요", "value": 0},
            {"label": "모름", "value": 9},
            {"label": "형제자매 없음", "value": 8},
        ],
    },
    {
        "no": 10,
        "field": "alcohol_ever",
        "text": "지금까지 술을 마셔 본 적이 있나요?",
        "type": "SINGLE",
        "options": [{"label": "없다", "value": 1}, {"label": "있다", "value": 2}],
        "skip": [{"when": 1, "fields": ["alcohol_frequency", "alcohol_amount", "binge_frequency"]}],
    },
    {
        "no": 11,
        "field": "alcohol_frequency",
        "text": "최근 1년간 술을 얼마나 자주 마셨나요?",
        "type": "SINGLE",
        "options": [
            {"label": "전혀 마시지 않았다", "value": 1},
            {"label": "월 1회 미만", "value": 2},
            {"label": "월 1회 정도", "value": 3},
            {"label": "월 2~4회", "value": 4},
            {"label": "주 2~3회", "value": 5},
            {"label": "주 4회 이상", "value": 6},
        ],
        "skip": [{"when": 1, "fields": ["alcohol_amount", "binge_frequency"]}],
    },
    {
        "no": 12,
        "field": "alcohol_amount",
        "text": "술 마시는 날 한 번에 몇 잔 정도 마시나요?",
        "help": "술 종류 상관없이 마신 잔 수로 골라 주세요 (캔맥주 1개는 1.6잔)",
        "type": "SINGLE",
        "options": [
            {"label": "1~2잔", "value": 1},
            {"label": "3~4잔", "value": 2},
            {"label": "5~6잔", "value": 3},
            {"label": "7~9잔", "value": 4},
            {"label": "10잔 이상", "value": 5},
        ],
    },
    {
        "no": 13,
        "field": "binge_frequency",
        "text": "한 번의 술자리에서 남자 소주 7잔(맥주 5캔)·여자 5잔(맥주 3캔) 이상 마시는 날이 얼마나 있나요?",
        "text_by_gender": {
            "MALE": "한 번의 술자리에서 소주 7잔(맥주 5캔) 이상 마시는 날이 얼마나 있나요?",
            "FEMALE": "한 번의 술자리에서 소주 5잔(맥주 3캔) 이상 마시는 날이 얼마나 있나요?",
        },
        "type": "SINGLE",
        "options": [
            {"label": "전혀 없음", "value": 1},
            {"label": "월 1회 미만", "value": 2},
            {"label": "월 1회 정도", "value": 3},
            {"label": "주 1회 정도", "value": 4},
            {"label": "거의 매일", "value": 5},
        ],
    },
    {
        "no": 14,
        "field": "smoking_lifetime",
        "text": "지금까지 담배(궐련)를 얼마나 피웠나요?",
        "type": "SINGLE",
        "options": [
            {"label": "피운 적 없음", "value": 3},
            {"label": "5갑(100개비) 미만", "value": 1},
            {"label": "5갑(100개비) 이상", "value": 2},
        ],
        "skip": [{"when": 3, "fields": ["smoking_current", "cigarettes_per_day"]}],
    },
    {
        "no": 15,
        "field": "smoking_current",
        "text": "지금 담배(궐련)를 피우나요?",
        "type": "SINGLE",
        "options": [
            {"label": "매일", "value": 1},
            {"label": "가끔", "value": 2},
            {"label": "과거엔 피웠으나 지금은 안 피움", "value": 3},
        ],
        "skip": [{"when": 3, "fields": ["cigarettes_per_day"]}],
    },
    {
        "no": 16,
        "field": "cigarettes_per_day",
        "text": "하루 평균 몇 개비 피우나요?",
        "type": "NUMBER",
        "min": 1,
        "max": 60,
        "step": 1,
        "unit": "개비",
        "required": True,
    },
    {
        "no": 17,
        "field": "heated_tobacco",
        "text": "궐련형 전자담배를 사용하나요?",
        "type": "SINGLE",
        "options": [
            {"label": "사용한 적 없음", "value": 8},
            {"label": "매일", "value": 1},
            {"label": "가끔", "value": 2},
            {"label": "과거엔 썼으나 지금은 안 씀", "value": 3},
        ],
    },
    {
        "no": 18,
        "field": "liquid_ecig",
        "text": "액상형 전자담배를 사용하나요?",
        "type": "SINGLE",
        "options": [
            {"label": "사용한 적 없음", "value": 8},
            {"label": "지금 사용함", "value": 1},
            {"label": "지금은 안 씀", "value": 2},
        ],
    },
    {
        "no": 19,
        "field": "is_hypertension_diagnosed",
        "text": "고혈압 진단을 받은 적 있나요?",
        "type": "BOOLEAN",
        "options": [{"label": "예", "value": True}, {"label": "아니요", "value": False}],
    },
    {
        "no": 20,
        "field": "is_diabetes_diagnosed",
        "text": "당뇨 진단을 받은 적 있나요?",
        "type": "BOOLEAN",
        "options": [{"label": "예", "value": True}, {"label": "아니요", "value": False}],
    },
    {
        "no": 21,
        "field": "is_pregnant",
        "text": "지금 임신 중인가요?",
        "type": "BOOLEAN",
        "only_for": "FEMALE",
        "options": [{"label": "예", "value": True}, {"label": "아니요", "value": False}],
    },
]

QUESTION_BY_FIELD: Final[dict[str, dict[str, Any]]] = {q["field"]: q for q in QUESTIONS}

# WEEKLY(주간 재설문)에서 묻는 문항 (survey-mapping.md "재설문: 물음") — 2·3·10~16·19·20·21번
WEEKLY_FIELDS: Final = (
    "weight_kg",
    "waist_cm",
    "alcohol_ever",
    "alcohol_frequency",
    "alcohol_amount",
    "binge_frequency",
    "smoking_lifetime",
    "smoking_current",
    "cigarettes_per_day",
    "is_hypertension_diagnosed",
    "is_diabetes_diagnosed",
    "is_pregnant",
)

# WEEKLY에서 안 묻고 직전 행 값을 복사하는 문항 (키·가족력·전자담배). 값이 와도 무시
WEEKLY_COPIED_FIELDS: Final = tuple(q["field"] for q in QUESTIONS if q["field"] not in WEEKLY_FIELDS)

# WEEKLY에서 직전에 비해당(8·888)이었다가 이번에 해당될 때만 다시 묻는 문항 (13·16번)
ASK_WHEN_APPLICABLE_FIELDS: Final = ("binge_frequency", "cigarettes_per_day")

# 건너뛰기로 서버가 채우는 비해당 코드. 여기 없는 문항은 8
SKIPPED_CODE_BY_FIELD: Final[dict[str, int]] = {"cigarettes_per_day": 888}
DEFAULT_SKIPPED_CODE: Final = 8


def skipped_code(field: str) -> int:
    return SKIPPED_CODE_BY_FIELD.get(field, DEFAULT_SKIPPED_CODE)


def is_not_applicable_code(field: str, value: Any) -> bool:
    """저장된 값이 건너뛰기로 채운 비해당 코드인지 (13번 8, 16번 888)."""
    return value == skipped_code(field)


# 21문항을 전부 묻는 설문 (EDIT는 가입 설문과 같은 문항·같은 검사, 정할 것 1번)
FULL_SURVEY_KINDS: Final = frozenset({SurveyKind.ONBOARDING, SurveyKind.EDIT})


def build_questions(kind: SurveyKind, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """3-6 응답 본문을 만든다.

    ONBOARDING·EDIT는 21문항 전부, WEEKLY는 재설문 문항만 남기고 13·16번에 직전 행을 보고 ask_when_applicable을 붙인다.
    previous: 사용자의 직전 설문 행 값 (WEEKLY에 필요, 없는 경우는 호출 쪽에서 409로 막음)
    """
    if kind in FULL_SURVEY_KINDS:
        questions = copy.deepcopy(QUESTIONS)
    else:
        if previous is None:
            raise ValueError("WEEKLY 문항은 직전 설문 행이 있어야 만들 수 있음")
        questions = [copy.deepcopy(q) for q in QUESTIONS if q["field"] in WEEKLY_FIELDS]
        for question in questions:
            field = question["field"]
            if field in ASK_WHEN_APPLICABLE_FIELDS:
                question["ask_when_applicable"] = is_not_applicable_code(field, previous.get(field))
    return {"survey_version": SURVEY_VERSION, "kind": kind.value, "questions": questions}
