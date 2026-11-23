from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.factories import make_signup_data

LOGOUT_URL = "/api/v1/auth/logout"


class TestLogoutAPI(TestCase):
    async def test_logout_clears_refresh_cookie(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            signup = await client.post("/api/v1/auth/signup", json=make_signup_data("logout@example.com"))
            access_token = signup.json()["access_token"]
            response = await client.post(LOGOUT_URL, headers={"Authorization": f"Bearer {access_token}"})

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        set_cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token="))
        assert "Max-Age=0" in set_cookie

    async def test_logout_without_token(self):
        # access 토큰이 만료된 뒤에도 쿠키를 지울 수 있게 로그인 없이 항상 204
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(LOGOUT_URL)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        set_cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token="))
        assert "Max-Age=0" in set_cookie
