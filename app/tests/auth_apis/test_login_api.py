from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.main import app
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data


class TestLoginAPI(TestCase):
    async def test_login_success(self):
        # 먼저 사용자 등록
        signup_data = make_signup_data(
            "login_test@example.com", nickname="로그인테스터", gender="FEMALE", birthday="1995-05-05"
        )
        login_data = {"email": "login_test@example.com", "password": DEFAULT_PASSWORD}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)

            # 로그인 시도
            response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()
        # 쿠키 검증 대신 응답 헤더 확인
        assert any("refresh_token" in header for header in response.headers.get_list("set-cookie"))

    async def test_login_refresh_cookie_max_age(self):
        signup_data = make_signup_data("cookie_test@example.com", nickname="쿠키테스터")
        login_data = {"email": "cookie_test@example.com", "password": DEFAULT_PASSWORD}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)
            response = await client.post("/api/v1/auth/login", json=login_data)

        set_cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token="))
        # refresh 만료(14일)를 초로. 예전엔 access exp 타임스탬프를 넘겨서 2080년대까지 살아 있었음
        assert f"Max-Age={config.REFRESH_TOKEN_EXPIRE_MINUTES * 60}" in set_cookie
        assert "expires" not in set_cookie.lower()
        assert "HttpOnly" in set_cookie

    async def test_login_invalid_credentials(self):
        login_data = {"email": "nonexistent@example.com", "password": "WrongPassword123!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json=login_data)

        # AuthService.authenticate 에서 실패 시 HTTP_400_BAD_REQUEST 발생
        assert response.status_code == status.HTTP_400_BAD_REQUEST
