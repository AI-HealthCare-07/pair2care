"""3-2 최근 설문 · 3-3 설문 이력 · 3-5 설문 한 건 (api.md 3장)."""

from unittest.mock import patch

from httpx import AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.survey_apis.test_create_health_profile_api import URL, new_client, onboarding_body, weekly_body

LATEST_URL = f"{URL}/latest"


@patch(LOAD_MODEL_TARGET, new=fixed_model)
class TestReadHealthProfilesAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def three_surveys(self, client: AsyncClient) -> list[dict]:
        """가입 설문 → 재설문 2번. 3-1 응답의 health_profile 3개 (오래된 순)."""
        # 가입 설문은 비흡연 → 재설문도 비흡연 (흡연 시작이면 하루 개비 수를 새로 물어야 해서)
        weekly = {"smoking_lifetime": 3, "smoking_current": None}
        bodies = [onboarding_body(), weekly_body(weight_kg=77.0, **weekly), weekly_body(weight_kg=76.0, **weekly)]
        return [(await client.post(URL, json=body)).json()["health_profile"] for body in bodies]

    # ───── 3-2 ─────
    async def test_latest_404_before_survey(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-latest-404@example.com")
            response = await client.get(LATEST_URL)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "아직 설문 기록이 없어요."}

    async def test_latest_is_newest_survey_same_shape_as_create(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-latest@example.com")
            saved = await self.three_surveys(client)
            response = await client.get(LATEST_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == saved[-1]  # 3-1 응답의 health_profile과 같은 형태·값

    # ───── 3-3 ─────
    async def test_list_pages_newest_first_with_light_fields(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-list@example.com")
            saved = await self.three_surveys(client)
            first = (await client.get(URL, params={"limit": 2})).json()
            second = (await client.get(URL, params={"limit": 2, "cursor": first["next_cursor"]})).json()

        assert [item["id"] for item in first["items"]] == [saved[2]["id"], saved[1]["id"]]
        assert first["next_cursor"] == saved[1]["id"]
        assert [item["id"] for item in second["items"]] == [saved[0]["id"]]
        assert second["next_cursor"] is None
        assert set(first["items"][0]) == {"id", "kind", "weight_kg", "waist_cm", "created_at"}
        assert first["items"][0]["weight_kg"] == 76.0

    async def test_list_filters_kind(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-list-kind@example.com")
            await self.three_surveys(client)
            weekly = (await client.get(URL, params={"kind": "WEEKLY"})).json()
            onboarding = (await client.get(URL, params={"kind": "ONBOARDING"})).json()

        assert [item["kind"] for item in weekly["items"]] == ["WEEKLY", "WEEKLY"]
        assert [item["kind"] for item in onboarding["items"]] == ["ONBOARDING"]

    async def test_list_with_someone_elses_cursor_is_404(self) -> None:
        async with new_client() as other:
            await self.login(other, "hp-cursor-other@example.com")
            others = await self.three_surveys(other)
        async with new_client() as client:
            await self.login(client, "hp-cursor-me@example.com")
            await self.three_surveys(client)
            response = await client.get(URL, params={"cursor": others[0]["id"]})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "설문 기록을 찾을 수 없어요."}

    async def test_list_empty_before_survey(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-list-empty@example.com")
            response = await client.get(URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"items": [], "next_cursor": None}

    # ───── 3-5 ─────
    async def test_get_one_same_as_create_and_others_are_404(self) -> None:
        async with new_client() as other:
            await self.login(other, "hp-one-other@example.com")
            others = await self.three_surveys(other)
        async with new_client() as client:
            await self.login(client, "hp-one-me@example.com")
            mine = await self.three_surveys(client)
            own = await client.get(f"{URL}/{mine[0]['id']}")
            not_mine = await client.get(f"{URL}/{others[0]['id']}")
            questions = await client.get(f"{URL}/questions", params={"kind": "WEEKLY"})

        assert own.status_code == status.HTTP_200_OK
        assert own.json() == mine[0]
        assert not_mine.status_code == status.HTTP_404_NOT_FOUND
        assert not_mine.json() == {"detail": "설문 기록을 찾을 수 없어요."}
        assert questions.status_code == status.HTTP_200_OK  # /{profile_id}가 /questions를 가로채지 않음
