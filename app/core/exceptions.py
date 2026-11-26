"""공통 에러 응답 (api.md 1장 "에러").

기본은 FastAPI HTTPException 그대로 `{"detail": "한국어 문구"}`.
프론트가 문구 글자가 아니라 종류로 갈라서 처리해야 하는 에러에만 AppError로 `code`를 붙임
→ `{"detail": "한국어 문구", "code": "SURVEY_VERSION_MISMATCH"}`
어느 문항인지 알려야 하는 400은 `field`도 같이 → `{"detail": ..., "code": "SURVEY_FIELD_INVALID", "field": "alcohol_amount"}`

HTTPException(detail={...})로 던지면 `{"detail": {"detail": ..., "code": ...}}`로 한 번 더 감싸지므로
AppError + 전용 핸들러로 같은 높이에 내려줌.
"""

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse


class ErrorCode(StrEnum):
    """프론트가 갈라 처리하는 에러 종류. 새로 붙이면 api.md 1장 표에도 추가."""

    SURVEY_VERSION_MISMATCH = "SURVEY_VERSION_MISMATCH"  # 3-1 → 3-6 다시 불러오기
    ONBOARDING_REQUIRED = "ONBOARDING_REQUIRED"  # 3-1·3-6 WEEKLY인데 가입 설문 없음 → S-06
    ONBOARDING_ALREADY_DONE = "ONBOARDING_ALREADY_DONE"  # 3-1 가입 설문 두 번 → 홈
    SURVEY_FIELD_INVALID = "SURVEY_FIELD_INVALID"  # 3-1 문항 규칙 위반, field 문항으로 이동
    SIGNUP_UNDER_14 = "SIGNUP_UNDER_14"  # 2-1 만 14세 미만, field=birthday
    SIGNUP_TERMS_REQUIRED = "SIGNUP_TERMS_REQUIRED"  # 2-1 필수 약관 미동의·옛 버전, field=consents


class AppError(Exception):
    """`code`가 필요한 에러. code가 필요 없으면 HTTPException을 그대로 씀."""

    def __init__(self, status_code: int, detail: str, code: ErrorCode, field: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.field = field  # 프론트가 이동할 문항 이름 (없으면 응답에서 뺌)


async def app_error_handler(_: Request, exc: Exception) -> ORJSONResponse:
    # Starlette 핸들러 시그니처가 Exception이라 좁혀 줌. AppError로만 등록하므로 다른 예외는 오지 않지만,
    # assert는 python -O에서 사라지므로 쓰지 않고 그대로 다시 던짐
    if not isinstance(exc, AppError):
        raise exc
    content: dict[str, str] = {"detail": exc.detail, "code": exc.code.value}
    if exc.field is not None:
        content["field"] = exc.field
    return ORJSONResponse(status_code=exc.status_code, content=content)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
