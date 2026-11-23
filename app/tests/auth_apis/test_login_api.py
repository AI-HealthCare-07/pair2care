from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.main import app
from app.services.auth import LOGIN_FAIL_KEY_PREFIX, LOGIN_LOCK_SECONDS
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

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "이메일 또는 비밀번호가 맞지 않아요."

    async def test_login_locked_after_5_failures(self):
        signup = make_signup_data("lock@example.com", nickname="잠금테스터")
        wrong = {"email": "lock@example.com", "password": "WrongPassword123!"}
        right = {"email": "lock@example.com", "password": DEFAULT_PASSWORD}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup)
            codes = [(await client.post("/api/v1/auth/login", json=wrong)).status_code for _ in range(5)]
            # 잠긴 뒤엔 맞는 비밀번호도 429
            locked = await client.post("/api/v1/auth/login", json=right)

        assert codes == [401, 401, 401, 401, 429]
        assert locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert locked.json()["detail"] == "로그인을 5번 틀려서 10분 뒤에 다시 시도할 수 있어요."

    async def test_login_lock_same_for_unknown_email(self):
        wrong = {"email": "nobody@example.com", "password": "WrongPassword123!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            codes = [(await client.post("/api/v1/auth/login", json=wrong)).status_code for _ in range(5)]
        # 가입 안 된 이메일도 똑같이 잠겨야 가입 여부가 드러나지 않음
        assert codes == [401, 401, 401, 401, 429]

    async def test_login_success_resets_failures(self):
        signup = make_signup_data("reset@example.com", nickname="초기화테스터")
        wrong = {"email": "reset@example.com", "password": "WrongPassword123!"}
        right = {"email": "reset@example.com", "password": DEFAULT_PASSWORD}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup)
            for _ in range(4):
                await client.post("/api/v1/auth/login", json=wrong)
            ok = await client.post("/api/v1/auth/login", json=right)
            # 성공으로 횟수가 0이 됐으니 다시 틀려도 401
            again = await client.post("/api/v1/auth/login", json=wrong)

        assert ok.status_code == status.HTTP_200_OK
        assert again.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_failure_key_has_ttl(self):
        # 실패 횟수 키에 항상 만료가 걸려 있어야 함 (만료 없는 키가 남으면 영구 잠금)
        wrong = {"email": "ttl@example.com", "password": "WrongPassword123!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/login", json=wrong)

        async with Redis(host=config.REDIS_HOST, port=config.REDIS_PORT) as redis:
            ttl = await redis.ttl(f"{LOGIN_FAIL_KEY_PREFIX}ttl@example.com")
        assert 0 < ttl <= LOGIN_LOCK_SECONDS
