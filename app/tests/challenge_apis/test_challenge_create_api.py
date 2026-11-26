
"""8-7 SOLO 챌린지 생성 API 테스트."""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data

URL = "/api/v1/challenges"


def new_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


async def login(client: AsyncClient, email: str) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json=make_signup_data(email),
    )
    assert signup.status_code == status.HTTP_201_CREATED

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
        },
    )
    assert response.status_code == status.HTTP_200_OK

    client.headers["Authorization"] = (
        f"Bearer {response.json()['access_token']}"
    )


class TestChallengeCreateAPI(TestCase):

    async def test_create_solo_challenge(self) -> None:
        """로그인한 사용자는 SOLO 챌린지를 생성할 수 있다."""
        async with new_client() as client:
            await login(client, "chal-create@example.com")

            response = await client.post(
                URL,
                json={
                    "title": "10분 걷기",
                    "times_per_week": 3,
                    "mode": "SOLO",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["id"] > 0
        assert body["title"] == "10분 걷기"
        assert body["mode"] == "SOLO"

    async def test_invalid_times_per_week(self) -> None:
        """주간 목표 횟수가 1~7을 벗어나면 거부한다."""
        async with new_client() as client:
            await login(client, "chal-invalid@example.com")

            response = await client.post(
                URL,
                json={
                    "title": "10분 걷기",
                    "times_per_week": 8,
                    "mode": "SOLO",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_requires_login(self) -> None:
        """로그인하지 않은 사용자는 챌린지를 생성할 수 없다."""
        async with new_client() as client:
            response = await client.post(
                URL,
                json={
                    "title": "10분 걷기",
                    "times_per_week": 3,
                    "mode": "SOLO",
                },
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
