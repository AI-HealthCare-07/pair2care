from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import AppError, ErrorCode, register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            detail="설문 문항이 바뀌었어요. 다시 불러올게요.",
            code=ErrorCode.SURVEY_VERSION_MISMATCH,
        )

    @app.get("/field-error")
    async def raise_field_error() -> None:
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="한 번에 마시는 양을 골라 주세요.",
            code=ErrorCode.SURVEY_FIELD_INVALID,
            field="alcohol_amount",
        )

    @app.get("/http-error")
    async def raise_http_error() -> None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="키를 입력해 주세요.")

    return app


async def test_app_error_has_detail_and_code_at_same_level() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/app-error")

    assert response.status_code == status.HTTP_409_CONFLICT
    # HTTPException(detail={...})처럼 한 번 더 감싸지지 않음
    assert response.json() == {"detail": "설문 문항이 바뀌었어요. 다시 불러올게요.", "code": "SURVEY_VERSION_MISMATCH"}


async def test_http_exception_keeps_default_shape() -> None:
    # code가 필요 없는 에러는 기존 FastAPI 형식 그대로
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/http-error")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "키를 입력해 주세요."}


async def test_app_error_with_field() -> None:
    # 문항 규칙 400은 field까지 같은 높이에 (api.md 3-1)
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/field-error")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": "한 번에 마시는 양을 골라 주세요.",
        "code": "SURVEY_FIELD_INVALID",
        "field": "alcohol_amount",
    }
