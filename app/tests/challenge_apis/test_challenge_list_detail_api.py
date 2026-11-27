"""8-9 챌린지 목록·상세 조회 API 테스트."""

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
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == status.HTTP_200_OK

    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def create_challenge(client: AsyncClient) -> int:
    response = await client.post(
        URL,
        json={
            "title": "10분 걷기",
            "times_per_week": 3,
            "mode": "SOLO",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestChallengeListDetailAPI(TestCase):
    async def test_list_active_challenges(self) -> None:
        """내 ACTIVE 챌린지 목록과 주간 목표를 조회한다."""
        async with new_client() as client:
            await login(client, "chal-list@example.com")
            challenge_id = await create_challenge(client)

            response = await client.get(
                URL,
                params={"status": "ACTIVE"},
            )

        assert response.status_code == status.HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1

        item = items[0]
        assert item["id"] == challenge_id
        assert item["title"] == "10분 걷기"
        assert item["mode"] == "SOLO"
        assert item["my_times_per_week"] == 3
        assert item["this_week"] == {"checked": 0, "target": 3}
        assert item["total_checked"] == 0
        assert item["is_owner"] is True

    async def test_get_challenge_detail(self) -> None:
        """상세 조회에서 참여자와 체크 기록을 확인한다."""
        async with new_client() as client:
            await login(client, "chal-detail@example.com")
            challenge_id = await create_challenge(client)

            response = await client.get(f"{URL}/{challenge_id}")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["id"] == challenge_id
        assert body["title"] == "10분 걷기"
        assert body["mode"] == "SOLO"
        assert body["times_per_week"] == 3
        assert body["my_checks"] == []
        assert len(body["participants"]) == 1
        assert body["participants"][0]["is_me"] is True

    async def test_other_user_cannot_view_challenge(self) -> None:
        """다른 사용자의 챌린지는 목록과 상세에서 숨긴다."""
        async with new_client() as owner:
            await login(owner, "chal-owner@example.com")
            challenge_id = await create_challenge(owner)

        async with new_client() as other:
            await login(other, "chal-other@example.com")

            list_response = await other.get(URL)
            detail_response = await other.get(f"{URL}/{challenge_id}")

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.json() == {"items": []}
        assert detail_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_requires_login(self) -> None:
        """로그인하지 않으면 목록과 상세를 조회할 수 없다."""
        async with new_client() as client:
            list_response = await client.get(URL)
            detail_response = await client.get(f"{URL}/1")

        assert list_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert detail_response.status_code == status.HTTP_401_UNAUTHORIZED
