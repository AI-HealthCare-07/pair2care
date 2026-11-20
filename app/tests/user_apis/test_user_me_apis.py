from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data


class TestUserMeApis(TestCase):
    async def test_get_user_me_success(self):
        # 사용자 등록 및 로그인
        email = "me@example.com"
        signup_data = make_signup_data(email, nickname="내정보테스터", gender="FEMALE", birthday="1992-02-02")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)

            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            access_token = login_response.json()["access_token"]

            # 내 정보 조회
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == email
        assert response.json()["nickname"] == "내정보테스터"

    async def test_update_user_me_success(self):
        # 사용자 등록 및 로그인
        email = "update_me@example.com"
        signup_data = make_signup_data(email, nickname="수정전", gender="MALE", birthday="1990-10-10")
        update_data = {"nickname": "수정후"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)

            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            access_token = login_response.json()["access_token"]

            # 내 정보 수정
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.patch("/api/v1/users/me", json=update_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nickname"] == "수정후"

    async def test_update_gender_birthday_forbidden(self):
        # 성별·생년월일은 직접 수정 불가 (api.md 2-5)
        email = "no_gender_change@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=make_signup_data(email))
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            gender_response = await client.patch("/api/v1/users/me", json={"gender": "FEMALE"}, headers=headers)
            birthday_response = await client.patch("/api/v1/users/me", json={"birthday": "1980-01-01"}, headers=headers)
        assert gender_response.status_code == status.HTTP_400_BAD_REQUEST
        assert birthday_response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_get_user_me_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
