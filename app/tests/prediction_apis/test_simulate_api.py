"""5-4 습관 시뮬레이션 API."""

from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.risk_predictions import Disease, RiskPrediction
from app.services.prediction.model import LogisticModel
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.prediction.test_model import make_model_dict
from app.tests.survey.test_validation import make_answers

SIMULATE_URL = "/api/v1/risk-predictions/simulate"
SURVEY_URL = "/api/v1/health-profiles"


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def onboarding_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers(**overrides)}


def bmi_model(disease: Disease) -> LogisticModel:
    """bmi 계수가 있는 테스트용 모델 (고정 모델은 계수가 0이라 점수가 안 바뀜)."""
    return LogisticModel.from_dict(make_model_dict(disease=disease.value, model_version=f"{disease.lower()}:test"))


@patch(LOAD_MODEL_TARGET, new=fixed_model)  # 모델 파일과 상관없이 당뇨 34 / 고혈압 21
class TestSimulateAPI(TestCase):
    async def login(self, client: AsyncClient, email: str, **signup: Any) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email, **signup))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def test_without_survey_is_404(self) -> None:
        async with new_client() as client:
            await self.login(client, "sim-404@example.com")
            response = await client.post(SIMULATE_URL, json={"changes": {"weight_kg": 75.0}})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_weight_loss_lowers_score_and_saves_nothing(self) -> None:
        with patch(LOAD_MODEL_TARGET, side_effect=bmi_model):
            async with new_client() as client:
                await self.login(client, "sim-weight@example.com")
                await client.post(SURVEY_URL, json=onboarding_body())
                rows_before = await RiskPrediction.all().count()
                response = await client.post(SIMULATE_URL, json={"changes": {"weight_kg": 65.0}})

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert [result["disease"] for result in body["results"]] == ["DIABETES", "HYPERTENSION"]
        diabetes = body["results"][0]
        assert diabetes["after"]["score"] < diabetes["before"]["score"]  # bmi 26.3 → 21.8
        assert body["managed_diseases"] == []
        assert body["skipped_reason"] is None
        assert await RiskPrediction.all().count() == rows_before  # 저장 안 함

    async def test_before_uses_saved_score(self) -> None:
        # 고정 모델로 저장된 34점이 before, 계수 0이라 after도 34
        async with new_client() as client:
            await self.login(client, "sim-saved@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            response = await client.post(SIMULATE_URL, json={"changes": {"alcohol_frequency": 1}})

        diabetes = response.json()["results"][0]
        assert diabetes == {
            "disease": "DIABETES",
            "before": {"score": 34, "level": "CAUTION"},
            "after": {"score": 34, "level": "CAUTION"},
        }

    async def test_other_field_400_before_format_422(self) -> None:
        async with new_client() as client:
            await self.login(client, "sim-400@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            other = await client.post(SIMULATE_URL, json={"changes": {"height_cm": "abc"}})
            bad_value = await client.post(SIMULATE_URL, json={"changes": {"alcohol_frequency": 8}})

        assert other.status_code == status.HTTP_400_BAD_REQUEST
        assert other.json() == {"detail": "체중·음주·흡연만 바꿔 볼 수 있어요."}
        assert bad_value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_not_applicable_habit_400(self) -> None:
        async with new_client() as client:
            await self.login(client, "sim-na@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())  # 담배 피운 적 없음
            response = await client.post(SIMULATE_URL, json={"changes": {"smoking_current": 3}})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "지금 해당하지 않는 습관은 바꿔 볼 수 없어요."}

    async def test_diagnosed_disease_excluded(self) -> None:
        async with new_client() as client:
            await self.login(client, "sim-managed@example.com")
            await client.post(SURVEY_URL, json=onboarding_body(is_diabetes_diagnosed=True))
            response = await client.post(SIMULATE_URL, json={"changes": {"weight_kg": 70.0}})

        body = response.json()
        assert [result["disease"] for result in body["results"]] == ["HYPERTENSION"]
        assert body["managed_diseases"] == ["DIABETES"]

    async def test_pregnant_has_no_results(self) -> None:
        async with new_client() as client:
            await self.login(client, "sim-pregnant@example.com", gender="FEMALE")
            await client.post(SURVEY_URL, json=onboarding_body(is_pregnant=True))
            response = await client.post(SIMULATE_URL, json={"changes": {"weight_kg": 60.0}})

        assert response.json() == {"results": [], "managed_diseases": [], "skipped_reason": "PREGNANT"}

    async def test_before_recomputed_when_model_version_changed(self) -> None:
        # 고정 모델(34점)로 저장된 뒤 모델이 바뀌면, before도 새 모델로 다시 계산해 같은 모델끼리 비교
        async with new_client() as client:
            await self.login(client, "sim-version@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            with patch(LOAD_MODEL_TARGET, side_effect=bmi_model):
                response = await client.post(SIMULATE_URL, json={"changes": {"weight_kg": 65.0}})

        diabetes = response.json()["results"][0]
        assert diabetes["before"]["score"] != 34
        assert diabetes["after"]["score"] < diabetes["before"]["score"]
