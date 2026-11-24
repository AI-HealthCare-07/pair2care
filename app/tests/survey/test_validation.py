"""3-1 설문 규칙 검사·채우기 (DB 없이 도는 순수 테스트, 3-1 에러 목록 11/23)."""

from typing import Any

import pytest

from app.models.health_profiles import SurveyKind
from app.models.users import Gender
from app.services.survey.validation import SurveyFieldError, resolve_answers


def make_answers(**overrides: Any) -> dict[str, Any]:
    """api.md 3-1 요청 예시 (술 마심·비흡연 남성). 바꿀 문항만 overrides로."""
    answers: dict[str, Any] = {
        "height_cm": 172.5,
        "weight_kg": 78.2,
        "waist_cm": None,
        "father_diabetes_history": 1,
        "mother_diabetes_history": 0,
        "sibling_diabetes_history": 8,
        "father_hypertension_history": 9,
        "mother_hypertension_history": 1,
        "sibling_hypertension_history": 0,
        "alcohol_ever": 2,
        "alcohol_frequency": 5,
        "alcohol_amount": 3,
        "binge_frequency": 2,
        "smoking_lifetime": 3,
        "smoking_current": None,
        "cigarettes_per_day": None,
        "heated_tobacco": 8,
        "liquid_ecig": 8,
        "is_hypertension_diagnosed": False,
        "is_diabetes_diagnosed": False,
        "is_pregnant": None,
    }
    answers.update(overrides)
    return answers


def make_previous(**overrides: Any) -> dict[str, Any]:
    """직전 설문 행 (가입 설문 저장 결과). 흡연자, 술은 마셔 본 적 없음."""
    previous = make_answers(
        alcohol_ever=1,
        alcohol_frequency=8,
        alcohol_amount=8,
        binge_frequency=8,
        smoking_lifetime=2,
        smoking_current=1,
        cigarettes_per_day=10,
    )
    previous.update(overrides)
    return previous


def assert_field_error(exc: pytest.ExceptionInfo[SurveyFieldError], field: str, detail: str) -> None:
    assert exc.value.status_code == 400
    assert exc.value.code == "SURVEY_FIELD_INVALID"
    assert exc.value.field == field
    assert exc.value.detail == detail


# ---------- ONBOARDING ----------


def test_onboarding_fills_skipped_smoking_codes() -> None:
    # 피운 적 없음(3) → 15번 8, 16번 888을 서버가 채움
    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, make_answers())

    assert resolved["smoking_current"] == 8
    assert resolved["cigarettes_per_day"] == 888
    assert resolved["binge_frequency"] == 2
    assert len(resolved) == 21


def test_onboarding_non_drinker_fills_8() -> None:
    answers = make_answers(alcohol_ever=1, alcohol_frequency=None, alcohol_amount=None, binge_frequency=None)

    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert (resolved["alcohol_frequency"], resolved["alcohol_amount"], resolved["binge_frequency"]) == (8, 8, 8)


def test_no_drinking_last_year_skips_amount_and_binge() -> None:
    # 11번 "전혀"(1)는 사용자가 고른 값이라 그대로, 12·13번만 8
    answers = make_answers(alcohol_frequency=1, alcohol_amount=None, binge_frequency=None)

    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert (resolved["alcohol_frequency"], resolved["alcohol_amount"], resolved["binge_frequency"]) == (1, 8, 8)


def test_user_chosen_8_is_kept() -> None:
    # 형제자매 없음·전자담배 사용한 적 없음 8은 정상 보기 (건너뛰기 8과 다름)
    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, make_answers())

    assert resolved["sibling_diabetes_history"] == 8
    assert resolved["heated_tobacco"] == 8


def test_waist_is_optional() -> None:
    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, make_answers(waist_cm=None))

    assert resolved["waist_cm"] is None


def test_skip_violation_is_400_not_overwritten() -> None:
    # 마셔 본 적 없는데 음주 횟수가 옴 → 조용히 8로 바꾸지 않고 400 (프론트 버그를 드러냄)
    answers = make_answers(alcohol_ever=1, alcohol_frequency=4, alcohol_amount=None, binge_frequency=None)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert_field_error(exc, "alcohol_frequency", "술을 마셔 본 적이 없으면 음주 횟수는 보낼 수 없어요.")


def test_skip_violation_by_current_smoking() -> None:
    answers = make_answers(smoking_lifetime=2, smoking_current=3, cigarettes_per_day=5)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert_field_error(exc, "cigarettes_per_day", "지금 담배를 피우지 않으면 하루 흡연량은 보낼 수 없어요.")


def test_missing_applicable_answer_is_400() -> None:
    answers = make_answers(alcohol_amount=None)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert_field_error(exc, "alcohol_amount", "한 번에 마시는 양을 골라 주세요.")


def test_first_error_by_question_number() -> None:
    # 1번 키와 12번 음주량이 둘 다 빠지면 번호가 앞선 1번 하나만
    answers = make_answers(height_cm=None, alcohol_amount=None)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert_field_error(exc, "height_cm", "키를 입력해 주세요.")


# ---------- 성별 조건 (21번) ----------


def test_male_with_pregnancy_is_400() -> None:
    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, make_answers(is_pregnant=False))

    assert_field_error(exc, "is_pregnant", "임신 여부는 여성만 답할 수 있어요.")


def test_female_without_pregnancy_is_400() -> None:
    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.FEMALE, make_answers(is_pregnant=None))

    assert_field_error(exc, "is_pregnant", "임신 여부를 골라 주세요.")


def test_gender_checked_before_question_order() -> None:
    # 성별 400이 문항 번호 순 400보다 먼저 (에러 목록 검사 순서 ③ → ④)
    answers = make_answers(height_cm=None, is_pregnant=True)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, answers)

    assert exc.value.field == "is_pregnant"


def test_female_pregnancy_saved() -> None:
    resolved = resolve_answers(SurveyKind.ONBOARDING, Gender.FEMALE, make_answers(is_pregnant=False))

    assert resolved["is_pregnant"] is False


# ---------- WEEKLY ----------


def make_weekly_answers(**overrides: Any) -> dict[str, Any]:
    """WEEKLY 요청: 안 묻는 문항(키·가족력·전자담배)은 보내지 않음. 이번에도 안 마시고 계속 흡연."""
    answers: dict[str, Any] = {
        "weight_kg": 76.0,
        "waist_cm": None,
        "alcohol_ever": 1,
        "alcohol_frequency": None,
        "alcohol_amount": None,
        "binge_frequency": None,
        "smoking_lifetime": 2,
        "smoking_current": 1,
        "cigarettes_per_day": None,
        "is_hypertension_diagnosed": False,
        "is_diabetes_diagnosed": False,
        "is_pregnant": None,
    }
    answers.update(overrides)
    return answers


def test_weekly_copies_not_asked_fields_and_ignores_sent_values() -> None:
    # 키·가족력·전자담배는 안 묻는 문항 → 값이 와도 400이 아니라 무시하고 직전 값 복사
    answers = make_weekly_answers(height_cm=180.0, heated_tobacco=1)

    resolved = resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert resolved["height_cm"] == 172.5
    assert resolved["heated_tobacco"] == 8
    assert resolved["father_diabetes_history"] == 1
    assert resolved["weight_kg"] == 76.0


def test_weekly_still_applicable_copies_previous() -> None:
    # 직전에도 흡연(10개비) → 16번은 다시 안 물음. 값이 와도 무시하고 10 복사
    answers = make_weekly_answers(cigarettes_per_day=20)

    resolved = resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert resolved["cigarettes_per_day"] == 10


def test_weekly_newly_applicable_requires_answer() -> None:
    # 직전엔 술을 마셔 본 적 없음(13번 8) → 이번에 마시면 13번을 다시 받아야 함
    answers = make_weekly_answers(alcohol_ever=2, alcohol_frequency=4, alcohol_amount=2, binge_frequency=None)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert_field_error(exc, "binge_frequency", "한 번에 많이 마시는 날이 얼마나 되는지 골라 주세요.")


def test_weekly_newly_applicable_saves_answer() -> None:
    answers = make_weekly_answers(alcohol_ever=2, alcohol_frequency=4, alcohol_amount=2, binge_frequency=3)

    resolved = resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert resolved["binge_frequency"] == 3


def test_weekly_newly_not_applicable_fills_888() -> None:
    # 이번에 끊음(3) → 16번 888 자동
    answers = make_weekly_answers(smoking_current=3)

    resolved = resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert resolved["cigarettes_per_day"] == 888


def test_weekly_not_applicable_with_value_is_400() -> None:
    # ask_when_applicable이 false여도, 이번 답으로 비해당인데 값이 오면 건너뛰기 위반 400
    answers = make_weekly_answers(smoking_current=3, cigarettes_per_day=5)

    with pytest.raises(SurveyFieldError) as exc:
        resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous())

    assert exc.value.field == "cigarettes_per_day"


def test_weekly_waist_is_not_copied() -> None:
    # 허리둘레는 재설문 때 안 보내면 null (직전 값 복사 안 함)
    answers = make_weekly_answers(waist_cm=None)

    resolved = resolve_answers(SurveyKind.WEEKLY, Gender.MALE, answers, make_previous(waist_cm=85.0))

    assert resolved["waist_cm"] is None


def test_weekly_without_previous_is_programming_error() -> None:
    # 직전 행 없는 WEEKLY는 서비스가 409로 먼저 막아야 함
    with pytest.raises(ValueError):
        resolve_answers(SurveyKind.WEEKLY, Gender.MALE, make_weekly_answers())
