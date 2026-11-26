from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.user_consents import UserConsent
from app.services.auth import AuthService
from app.tests.factories import make_consents, make_signup_data

SIGNUP_URL = "/api/v1/auth/signup"


class TestSignupAPI(TestCase):
    async def test_signup_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(SIGNUP_URL, json=make_signup_data("test@example.com"))

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        # 가입하면 바로 로그인 상태 (api.md 2-1)
        assert body["access_token"]
        assert body["user"]["nickname"] == "테스터"
        assert body["has_health_profile"] is False
        assert "phone_number" not in body["user"]
        assert any("refresh_token" in h for h in response.headers.get_list("set-cookie"))
        # 동의 3종이 같이 저장됨
        assert await UserConsent.filter(user_id=body["user"]["id"], is_agreed=True).count() == 3

    async def test_signup_duplicate_email(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(SIGNUP_URL, json=make_signup_data("dup@example.com"))
            response = await client.post(SIGNUP_URL, json=make_signup_data("dup@example.com"))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "이미 가입된 이메일이에요."

    async def test_signup_race_duplicate_email(self):
        # 동시 가입 재현: 두 요청이 모두 중복 체크를 통과한 상황 → DB unique에서 막혀도 500이 아니라 409
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(SIGNUP_URL, json=make_signup_data("race@example.com"))
            with patch.object(AuthService, "check_email_exists", AsyncMock()):
                response = await client.post(SIGNUP_URL, json=make_signup_data("race@example.com"))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "이미 가입된 이메일이에요."

    async def test_signup_invalid_email(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(SIGNUP_URL, json=make_signup_data("invalid-email"))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_signup_invalid_password(self):
        # 8자 미만 / 영문·숫자·특수문자 중 빠짐 / 공백·한글 포함
        bad_passwords = ["Pair2c!", "12345678", "password", "!!!!!!!!", "pair2care1", "pair 2care1!", "pair2careㅁ1!"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for i, password in enumerate(bad_passwords):
                data = make_signup_data(f"pw{i}@example.com", password=password)
                response = await client.post(SIGNUP_URL, json=data)
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, password

    async def test_signup_missing_consent(self):
        consents = make_consents()
        consents[2]["is_agreed"] = False  # 민감정보 동의 안 함
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(SIGNUP_URL, json=make_signup_data("consent@example.com", consents=consents))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "detail": "필수 약관에 모두 동의해 주세요.",
            "code": "SIGNUP_TERMS_REQUIRED",
            "field": "consents",
        }

    async def test_signup_old_terms_version(self):
        data = make_signup_data("old@example.com", consents=make_consents(version="v0.9"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(SIGNUP_URL, json=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "SIGNUP_TERMS_REQUIRED"

    async def test_signup_under_14(self):
        # 422(형식 오류)가 아니라 400 + code·field → 화면이 생년월일 칸 아래에 문구를 띄움 (api.md 2-1)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(SIGNUP_URL, json=make_signup_data("kid@example.com", birthday="2020-01-01"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "detail": "만 14세 미만은 가입할 수 없어요.",
            "code": "SIGNUP_UNDER_14",
            "field": "birthday",
        }

    async def test_signup_bad_birthday_format_is_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                SIGNUP_URL, json=make_signup_data("bad-date@example.com", birthday="1990-13-40")
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
