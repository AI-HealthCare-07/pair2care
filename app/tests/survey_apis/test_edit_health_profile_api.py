"""3-4 마이에서 설문 고치기 (kind=EDIT, 정할 것 1번 11/26 확정)."""

from typing import Any
from unittest.mock import patch

from httpx import AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.models.health_profiles import HealthProfile
from app.models.risk_predictions import RiskPrediction
from app.services.survey.questions import QUESTIONS
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.survey_apis.test_create_health_profile_api import URL, new_client, onboarding_body, weekly_body

QUESTIONS_URL = f"{URL}/questions"


def edit_body(**overrides: Any) -> dict[str, Any]:
    return {**onboarding_body(**overrides), "kind": "EDIT"}


@patch(LOAD_MODEL_TARGET, new=fixed_model)
class TestEditHealthProfileAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def test_edit_before_onboarding_is_409(self) -> None:
        async with new_client() as client:
            await self.login(client, "edit-first@example.com")
            saved = await client.post(URL, json=edit_body())
            questions = await client.get(QUESTIONS_URL, params={"kind": "EDIT"})

        for response in (saved, questions):
            assert response.status_code == status.HTTP_409_CONFLICT
            assert response.json()["code"] == "ONBOARDING_REQUIRED"

    async def test_edit_saves_new_row_with_all_questions_and_predicts(self) -> None:
        async with new_client() as client:
            await self.login(client, "edit-save@example.com")
            first = (await client.post(URL, json=onboarding_body())).json()["health_profile"]
            edited = await client.post(URL, json=edit_body(height_cm=180.0, mother_diabetes_history=1))

        assert edited.status_code == status.HTTP_201_CREATED
        body = edited.json()
        profile = body["health_profile"]
        assert profile["kind"] == "EDIT"
        assert profile["id"] != first["id"]  # 고치지 않고 새 행
        assert profile["height_cm"] == 180.0  # 재설문에선 못 바꾸는 키·가족력이 바뀜
        assert profile["mother_diabetes_history"] == 1
        assert await HealthProfile.filter(id=first["id"], height_cm=172.5).exists()  # 옛 행은 그대로
        assert body["prediction_error"] is False
        assert await RiskPrediction.filter(health_profile_id=profile["id"]).count() == 2  # 다시 예측

    async def test_edit_uses_onboarding_skip_rules(self) -> None:
        # 숨겨지는 문항(비흡연인데 하루 개비 수)에 값이 오면 가입 설문과 같은 400
        async with new_client() as client:
            await self.login(client, "edit-skip@example.com")
            await client.post(URL, json=onboarding_body())
            response = await client.post(URL, json=edit_body(cigarettes_per_day=10))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["field"] == "cigarettes_per_day"

    async def test_weekly_after_edit_copies_edited_values(self) -> None:
        async with new_client() as client:
            await self.login(client, "edit-weekly@example.com")
            await client.post(URL, json=onboarding_body())
            await client.post(URL, json=edit_body(height_cm=180.0))
            weekly = await client.post(URL, json=weekly_body(smoking_lifetime=3, smoking_current=None))

        assert weekly.status_code == status.HTTP_201_CREATED
        assert weekly.json()["health_profile"]["height_cm"] == 180.0  # 고친 키가 이어짐

    async def test_edit_questions_are_all_21(self) -> None:
        async with new_client() as client:
            await self.login(client, "edit-questions@example.com")
            await client.post(URL, json=onboarding_body())
            response = await client.get(QUESTIONS_URL, params={"kind": "EDIT"})
            onboarding = await client.get(QUESTIONS_URL, params={"kind": "ONBOARDING"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["kind"] == "EDIT"
        assert response.json()["survey_version"] == onboarding.json()["survey_version"]
        assert len(response.json()["questions"]) == len(QUESTIONS) == 21
        assert response.json()["questions"] == onboarding.json()["questions"]

    async def test_onboarding_again_points_to_edit(self) -> None:
        async with new_client() as client:
            await self.login(client, "edit-again@example.com")
            await client.post(URL, json=onboarding_body())
            again = await client.post(URL, json=onboarding_body())

        assert again.status_code == status.HTTP_409_CONFLICT
        assert again.json()["detail"] == "가입 설문은 이미 했어요. 바뀐 내용은 마이에서 고쳐 주세요."
