"""공통 에러 응답 (api.md 1장 "에러").

기본은 FastAPI HTTPException 그대로 `{"detail": "한국어 문구"}`.
프론트가 문구 글자가 아니라 종류로 갈라서 처리해야 하는 에러에만 AppError로 `code`를 붙임
→ `{"detail": "한국어 문구", "code": "SURVEY_VERSION_MISMATCH"}`

HTTPException(detail={...})로 던지면 `{"detail": {"detail": ..., "code": ...}}`로 한 번 더 감싸지므로
AppError + 전용 핸들러로 같은 높이에 내려줌.
"""

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse


class ErrorCode(StrEnum):
    """프론트가 갈라 처리하는 에러 종류. 새로 붙이면 api.md 1장 표에도 추가."""

    SURVEY_VERSION_MISMATCH = "SURVEY_VERSION_MISMATCH"  # 3-1 → 3-6 다시 불러오기
    ONBOARDING_REQUIRED = "ONBOARDING_REQUIRED"  # 3-1 WEEKLY인데 가입 설문 없음 → S-06
    ONBOARDING_ALREADY_DONE = "ONBOARDING_ALREADY_DONE"  # 3-1 가입 설문 두 번 → 홈


class AppError(Exception):
    """`code`가 필요한 에러. code가 필요 없으면 HTTPException을 그대로 씀."""

    def __init__(self, status_code: int, detail: str, code: ErrorCode) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


async def app_error_handler(_: Request, exc: Exception) -> ORJSONResponse:
    assert isinstance(exc, AppError)
    return ORJSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code.value})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
