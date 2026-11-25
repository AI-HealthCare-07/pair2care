from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.survey.test_validation import make_answers


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

    async def test_update_region_set_and_clear(self):
        # 날씨용 시·도: 고르기 → GET에 보임 → null로 해제 (api.md 2-5·11-7)
        email = "region@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=make_signup_data(email, nickname="지역테스터"))
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

            before = await client.get("/api/v1/users/me", headers=headers)
            set_response = await client.patch("/api/v1/users/me", json={"region": "경기"}, headers=headers)
            after_set = await client.get("/api/v1/users/me", headers=headers)
            clear_response = await client.patch("/api/v1/users/me", json={"region": None}, headers=headers)
        assert before.json()["region"] is None
        assert set_response.status_code == status.HTTP_200_OK
        assert set_response.json()["region"] == "경기"
        assert after_set.json()["region"] == "경기"
        assert after_set.json()["nickname"] == "지역테스터"  # region만 보내면 닉네임은 그대로
        assert clear_response.status_code == status.HTTP_200_OK
        assert clear_response.json()["region"] is None

    async def test_update_region_invalid_value(self):
        # 17개 시·도 밖의 값은 422
        email = "region_invalid@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=make_signup_data(email))
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            response = await client.patch("/api/v1/users/me", json={"region": "서울특별시"}, headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_update_nickname_keeps_region(self):
        # 닉네임만 바꾸면 이미 고른 지역은 지워지지 않음
        email = "region_keep@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=make_signup_data(email))
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            await client.patch("/api/v1/users/me", json={"region": "부산"}, headers=headers)
            response = await client.patch("/api/v1/users/me", json={"nickname": "새닉네임"}, headers=headers)
        assert response.json()["nickname"] == "새닉네임"
        assert response.json()["region"] == "부산"

    async def test_user_me_has_health_profile(self):
        # 가드가 설문 전이면 S-06으로 보내는 값 (api.md 2-5): 가입 직후 false → 가입 설문 저장 후 true
        email = "me_profile@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=make_signup_data(email))
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            )
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

            before = await client.get("/api/v1/users/me", headers=headers)
            survey = await client.post(
                "/api/v1/health-profiles",
                json={"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers()},
                headers=headers,
            )
            after = await client.get("/api/v1/users/me", headers=headers)
            patched = await client.patch("/api/v1/users/me", json={"nickname": "설문완료"}, headers=headers)
        assert before.json()["has_health_profile"] is False
        assert survey.status_code == status.HTTP_201_CREATED
        assert after.json()["has_health_profile"] is True
        assert patched.json()["has_health_profile"] is True  # PATCH 응답도 같은 모양
