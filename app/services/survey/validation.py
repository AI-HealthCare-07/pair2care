"""3-1 설문 저장 규칙 검사·채우기 (api.md 3-1, 3-1 에러 목록 11/23).

형식(타입·범위·보기 값) 422는 요청 DTO가, 버전·순서 409는 서비스가 먼저 막는다.
여기서는 그다음 단계만 본다: ③ 성별 조건 400 → ④ 문항 번호 순 400 (필수 누락·건너뛰기 위반), 첫 에러 하나만.

통과하면 저장할 21개 값을 돌려준다.
- 건너뛴 비해당 문항은 서버가 8 / 888로 채움 (프론트는 null로 보냄)
- WEEKLY에서 안 묻는 문항(키·가족력·전자담배)은 온 값을 무시하고 직전 행 값 복사
- WEEKLY 13·16번은 직전에 비해당이었다가 이번에 해당될 때만 받고, 계속 해당이면 직전 값 복사
DB와 상관없는 순수 함수라 직전 행은 dict로 받는다.
"""

from typing import Any, Final

from fastapi import status

from app.core.exceptions import AppError, ErrorCode
from app.models.health_profiles import SurveyKind
from app.models.users import Gender
from app.services.survey.questions import (
    ASK_WHEN_APPLICABLE_FIELDS,
    QUESTIONS,
    WEEKLY_COPIED_FIELDS,
    is_not_applicable_code,
    skipped_code,
)

PREGNANCY_FIELD: Final = "is_pregnant"
PREGNANCY_MALE_DETAIL: Final = "임신 여부는 여성만 답할 수 있어요."
PREGNANCY_MISSING_DETAIL: Final = "임신 여부를 골라 주세요."

# 해당자인데 값이 빠졌을 때 (3-1 에러 목록 3·4번)
MISSING_DETAIL_BY_FIELD: Final[dict[str, str]] = {
    "height_cm": "키를 입력해 주세요.",
    "weight_kg": "몸무게를 입력해 주세요.",
    "father_diabetes_history": "아버지의 당뇨 진단 여부를 골라 주세요.",
    "mother_diabetes_history": "어머니의 당뇨 진단 여부를 골라 주세요.",
    "sibling_diabetes_history": "형제자매의 당뇨 진단 여부를 골라 주세요.",
    "father_hypertension_history": "아버지의 고혈압 진단 여부를 골라 주세요.",
    "mother_hypertension_history": "어머니의 고혈압 진단 여부를 골라 주세요.",
    "sibling_hypertension_history": "형제자매의 고혈압 진단 여부를 골라 주세요.",
    "alcohol_ever": "술을 마셔 본 적이 있는지 골라 주세요.",
    "alcohol_frequency": "최근 1년간 술을 마신 횟수를 골라 주세요.",
    "alcohol_amount": "한 번에 마시는 양을 골라 주세요.",
    "binge_frequency": "한 번에 많이 마시는 날이 얼마나 되는지 골라 주세요.",
    "smoking_lifetime": "지금까지 담배를 피운 양을 골라 주세요.",
    "smoking_current": "지금 담배를 피우는지 골라 주세요.",
    "cigarettes_per_day": "하루에 피우는 개비 수를 입력해 주세요.",
    "heated_tobacco": "궐련형 전자담배 사용 여부를 골라 주세요.",
    "liquid_ecig": "액상형 전자담배 사용 여부를 골라 주세요.",
    "is_hypertension_diagnosed": "고혈압 진단 여부를 골라 주세요.",
    "is_diabetes_diagnosed": "당뇨 진단 여부를 골라 주세요.",
}

# 건너뛸 문항인데 값이 왔을 때 (3-1 에러 목록 5번). 키: (건너뛰게 만든 문항, 값이 온 문항)
SKIP_VIOLATION_DETAIL: Final[dict[tuple[str, str], str]] = {
    ("alcohol_ever", "alcohol_frequency"): "술을 마셔 본 적이 없으면 음주 횟수는 보낼 수 없어요.",
    ("alcohol_ever", "alcohol_amount"): "술을 마셔 본 적이 없으면 한 번 음주량은 보낼 수 없어요.",
    ("alcohol_ever", "binge_frequency"): "술을 마셔 본 적이 없으면 폭음 횟수는 보낼 수 없어요.",
    ("alcohol_frequency", "alcohol_amount"): "최근 1년간 술을 마시지 않았다면 한 번 음주량은 보낼 수 없어요.",
    ("alcohol_frequency", "binge_frequency"): "최근 1년간 술을 마시지 않았다면 폭음 횟수는 보낼 수 없어요.",
    ("smoking_lifetime", "smoking_current"): "담배를 피운 적이 없으면 현재 흡연 여부는 보낼 수 없어요.",
    ("smoking_lifetime", "cigarettes_per_day"): "담배를 피운 적이 없으면 하루 흡연량은 보낼 수 없어요.",
    ("smoking_current", "cigarettes_per_day"): "지금 담배를 피우지 않으면 하루 흡연량은 보낼 수 없어요.",
}


class SurveyFieldError(AppError):
    """문항 규칙 위반 400. 프론트는 field 문항으로 이동."""

    def __init__(self, detail: str, field: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            code=ErrorCode.SURVEY_FIELD_INVALID,
            field=field,
        )


def find_skipping_field(field: str, answers: dict[str, Any]) -> str | None:
    """이번 답 때문에 field가 건너뛰기 대상이면, 건너뛰게 만든 (번호가 가장 앞선) 문항 이름."""
    for question in QUESTIONS:
        parent_value = answers.get(question["field"])
        for rule in question.get("skip", []):
            if parent_value == rule["when"] and field in rule["fields"]:
                return str(question["field"])
    return None


def check_pregnancy(gender: Gender, answers: dict[str, Any]) -> None:
    """③ 성별 조건 (21번). 문항 번호 순 검사보다 먼저 본다."""
    value = answers.get(PREGNANCY_FIELD)
    if gender == Gender.MALE and value is not None:
        raise SurveyFieldError(PREGNANCY_MALE_DETAIL, PREGNANCY_FIELD)
    if gender == Gender.FEMALE and value is None:
        raise SurveyFieldError(PREGNANCY_MISSING_DETAIL, PREGNANCY_FIELD)


def resolve_answers(
    kind: SurveyKind,
    gender: Gender,
    answers: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """규칙을 검사하고 저장할 21개 값을 만든다. 위반이면 첫 번째 SurveyFieldError.

    answers: 요청 본문의 문항 값 (건너뛴 문항은 None)
    previous: 직전 설문 행 값. WEEKLY에서만 필요 (없으면 호출 쪽이 409 ONBOARDING_REQUIRED로 먼저 막음)
    """
    if kind == SurveyKind.WEEKLY and previous is None:
        raise ValueError("WEEKLY 저장은 직전 설문 행이 있어야 함")

    check_pregnancy(gender, answers)

    resolved: dict[str, Any] = {}
    for question in QUESTIONS:  # 배열 순서 = 문항 번호 순
        field = str(question["field"])
        resolved[field] = resolve_field(kind, question, answers, previous or {})
    return resolved


def resolve_field(
    kind: SurveyKind,
    question: dict[str, Any],
    answers: dict[str, Any],
    previous: dict[str, Any],
) -> Any:
    """문항 하나의 저장 값. 규칙 위반이면 SurveyFieldError. previous는 ONBOARDING이면 빈 dict."""
    field = str(question["field"])
    value = answers.get(field)

    if field == PREGNANCY_FIELD:
        return value  # check_pregnancy에서 이미 봄

    # WEEKLY에서 안 묻는 문항: 와도 무시하고 직전 값 복사
    if kind == SurveyKind.WEEKLY and field in WEEKLY_COPIED_FIELDS:
        return previous[field]

    # 이번 답으로 비해당 → 값이 오면 400, 안 오면 8 / 888
    skipping_field = find_skipping_field(field, answers)
    if skipping_field is not None:
        if value is not None:
            raise SurveyFieldError(SKIP_VIOLATION_DETAIL[(skipping_field, field)], field)
        return skipped_code(field)

    # WEEKLY 13·16번: 직전에도 해당이었으면 다시 묻지 않음 → 온 값은 무시하고 직전 값 복사
    if kind == SurveyKind.WEEKLY and field in ASK_WHEN_APPLICABLE_FIELDS:
        if not is_not_applicable_code(field, previous[field]):
            return previous[field]

    if value is None:
        if not question.get("required", True):
            return None  # 3번 허리둘레 (선택, WEEKLY도 복사 안 함)
        raise SurveyFieldError(MISSING_DETAIL_BY_FIELD[field], field)
    return value
