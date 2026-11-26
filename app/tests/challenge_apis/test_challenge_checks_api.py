
"""8-10 챌린지 완료 체크·취소 API 테스트."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data

URL = "/api/v1/challenges"
KST = ZoneInfo("Asia/Seoul")


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

    client.headers["Authorization"] = (
        f"Bearer {response.json()['access_token']}"
    )


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


class TestChallengeChecksAPI(TestCase):

    async def test_check_duplicate_and_uncheck(self) -> None:
        """체크 생성, 중복 방지, 체크 취소를 검증한다."""
        today = datetime.now(KST).date().isoformat()

        async with new_client() as client:
            await login(client, "check-owner@example.com")
            challenge_id = await create_challenge(client)

            check_url = f"{URL}/{challenge_id}/checks"
            payload = {"checked_on": today}

            first = await client.post(check_url, json=payload)
            assert first.status_code == status.HTTP_201_CREATED
            assert first.json()["checked_on"] == today
            assert first.json()["this_week"] == {
                "checked": 1,
                "target": 3,
            }

            second = await client.post(check_url, json=payload)
            assert second.status_code == status.HTTP_200_OK
            assert second.json()["this_week"]["checked"] == 1

            detail = await client.get(f"{URL}/{challenge_id}")
            assert detail.status_code == status.HTTP_200_OK
            assert detail.json()["my_checks"] == [today]

            deleted = await client.delete(
                f"{check_url}/{today}"
            )
            assert deleted.status_code == status.HTTP_204_NO_CONTENT

            detail_after = await client.get(
                f"{URL}/{challenge_id}"
            )
            assert detail_after.status_code == status.HTTP_200_OK
            assert detail_after.json()["my_checks"] == []

    async def test_invalid_check_date(self) -> None:
        """이틀 전 날짜의 체크와 취소는 거부한다."""
        invalid_date = (
            datetime.now(KST).date() - timedelta(days=2)
        ).isoformat()

        async with new_client() as client:
            await login(client, "check-date@example.com")
            challenge_id = await create_challenge(client)

            response = await client.post(
                f"{URL}/{challenge_id}/checks",
                json={"checked_on": invalid_date},
            )

            deleted = await client.delete(
                f"{URL}/{challenge_id}/checks/{invalid_date}"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert deleted.status_code == status.HTTP_400_BAD_REQUEST

    async def test_other_user_cannot_check(self) -> None:
        """다른 사용자는 내 챌린지를 체크하거나 취소할 수 없다."""
        today = datetime.now(KST).date().isoformat()

        async with new_client() as owner:
            await login(owner, "check-private-owner@example.com")
            challenge_id = await create_challenge(owner)

        async with new_client() as other:
            await login(other, "check-private-other@example.com")

            response = await other.post(
                f"{URL}/{challenge_id}/checks",
                json={"checked_on": today},
            )

            deleted = await other.delete(
                f"{URL}/{challenge_id}/checks/{today}"
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert deleted.status_code == status.HTTP_404_NOT_FOUND

    async def test_requires_login(self) -> None:
        """로그인하지 않으면 체크와 취소가 불가능하다."""
        today = datetime.now(KST).date().isoformat()

        async with new_client() as client:
            response = await client.post(
                f"{URL}/1/checks",
                json={"checked_on": today},
            )

            deleted = await client.delete(
                f"{URL}/1/checks/{today}"
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert deleted.status_code == status.HTTP_401_UNAUTHORIZED
