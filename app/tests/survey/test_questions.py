"""3-6 문항 정의 상수·응답 만들기 (DB 없이 도는 순수 테스트)."""

from app.models.health_profiles import SurveyKind
from app.services.survey.questions import (
    ASK_WHEN_APPLICABLE_FIELDS,
    QUESTIONS,
    SURVEY_VERSION,
    WEEKLY_COPIED_FIELDS,
    WEEKLY_FIELDS,
    build_questions,
)

HEALTH_PROFILE_ANSWER_FIELDS = (
    "height_cm",
    "weight_kg",
    "waist_cm",
    "father_diabetes_history",
    "mother_diabetes_history",
    "sibling_diabetes_history",
    "father_hypertension_history",
    "mother_hypertension_history",
    "sibling_hypertension_history",
    "alcohol_ever",
    "alcohol_frequency",
    "alcohol_amount",
    "binge_frequency",
    "smoking_lifetime",
    "smoking_current",
    "cigarettes_per_day",
    "heated_tobacco",
    "liquid_ecig",
    "is_hypertension_diagnosed",
    "is_diabetes_diagnosed",
    "is_pregnant",
)


def test_questions_cover_health_profile_columns_in_order() -> None:
    # 21문항이 health_profiles 설문 컬럼과 하나씩 맞고, 번호가 1부터 빠짐없이 이어짐
    assert [q["no"] for q in QUESTIONS] == list(range(1, 22))
    assert tuple(q["field"] for q in QUESTIONS) == HEALTH_PROFILE_ANSWER_FIELDS


def test_skip_rules_point_to_later_questions() -> None:
    # 건너뛰기는 항상 뒤 문항을 가리킴 (앞 문항을 건너뛰면 화면 순서가 꼬임)
    no_by_field = {q["field"]: q["no"] for q in QUESTIONS}
    for question in QUESTIONS:
        for rule in question.get("skip", []):
            assert all(no_by_field[field] > question["no"] for field in rule["fields"])


def test_weekly_and_copied_fields_split_all_questions() -> None:
    # 재설문 문항 2·3·10~16·19·20·21 / 나머지는 직전 값 복사 (survey-mapping.md 재설문 규칙)
    weekly_nos = [q["no"] for q in QUESTIONS if q["field"] in WEEKLY_FIELDS]
    assert weekly_nos == [2, 3, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21]
    assert set(WEEKLY_FIELDS) | set(WEEKLY_COPIED_FIELDS) == set(HEALTH_PROFILE_ANSWER_FIELDS)
    assert not set(WEEKLY_FIELDS) & set(WEEKLY_COPIED_FIELDS)
    assert set(ASK_WHEN_APPLICABLE_FIELDS) <= set(WEEKLY_FIELDS)


def test_onboarding_returns_all_questions_without_ask_flag() -> None:
    body = build_questions(SurveyKind.ONBOARDING)

    assert body["survey_version"] == SURVEY_VERSION
    assert body["kind"] == "ONBOARDING"
    assert len(body["questions"]) == 21
    assert all("ask_when_applicable" not in q for q in body["questions"])


def test_weekly_asks_again_only_when_previously_not_applicable() -> None:
    # 직전에 술을 안 마셔서 13번이 8 → 이번에 마시면 물음 / 16번은 직전에 해당(10개비) → 안 물음
    previous = {"binge_frequency": 8, "cigarettes_per_day": 10}

    body = build_questions(SurveyKind.WEEKLY, previous)

    flags = {q["field"]: q.get("ask_when_applicable") for q in body["questions"]}
    assert [q["no"] for q in body["questions"]] == [2, 3, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21]
    assert flags["binge_frequency"] is True
    assert flags["cigarettes_per_day"] is False
    assert flags["weight_kg"] is None  # 13·16번에만 붙음


def test_weekly_888_means_not_applicable() -> None:
    body = build_questions(SurveyKind.WEEKLY, {"binge_frequency": 3, "cigarettes_per_day": 888})

    flags = {q["field"]: q.get("ask_when_applicable") for q in body["questions"]}
    assert flags == flags | {"binge_frequency": False, "cigarettes_per_day": True}


def test_build_questions_does_not_change_constant() -> None:
    # 응답에 ask_when_applicable을 붙여도 서버 상수는 그대로 (다음 요청에 섞이면 안 됨)
    build_questions(SurveyKind.WEEKLY, {"binge_frequency": 8, "cigarettes_per_day": 888})

    assert all("ask_when_applicable" not in q for q in QUESTIONS)


def test_help_only_on_alcohol_amount() -> None:
    # 질문 아래 보조 설명 (M02). 표시용이라 survey_version과 상관없음
    helps = {q["field"]: q["help"] for q in QUESTIONS if "help" in q}
    assert helps == {"alcohol_amount": "술 종류 상관없이 마신 잔 수로 골라 주세요 (캔맥주 1개는 1.6잔)"}


def test_weekly_keeps_help() -> None:
    body = build_questions(SurveyKind.WEEKLY, {"binge_frequency": 8, "cigarettes_per_day": 888})

    amount = next(q for q in body["questions"] if q["field"] == "alcohol_amount")
    assert amount["help"].startswith("술 종류 상관없이")
