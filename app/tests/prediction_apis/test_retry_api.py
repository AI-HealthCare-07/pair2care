"""5-5 다시 계산 API."""

from unittest.mock import patch

from httpx import AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.models.risk_predictions import RiskPrediction
from app.models.users import User
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.prediction_apis.test_risk_prediction_api import LATEST_URL, SURVEY_URL, new_client, onboarding_body

RETRY_URL = "/api/v1/risk-predictions/retry"


def broken_model(*_: object) -> None:
    raise ValueError("모델 파일을 읽지 못함 (테스트)")


@patch(LOAD_MODEL_TARGET, new=fixed_model)  # 모델 파일과 상관없이 당뇨 34 / 고혈압 21
class TestRetryAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def failed_onboarding(self, client: AsyncClient, email: str) -> None:
        """가입 설문은 저장됐지만 예측이 실패한 상태 (3-1 prediction_error: true)."""
        await self.login(client, email)
        with patch(LOAD_MODEL_TARGET, new=broken_model):
            created = await client.post(SURVEY_URL, json=onboarding_body())
        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["prediction_error"] is True

    async def test_without_survey_is_404(self) -> None:
        async with new_client() as client:
            await self.login(client, "retry-404@example.com")
            response = await client.post(RETRY_URL)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "아직 설문 기록이 없어요."}

    async def test_retry_after_failed_prediction_saves_rows(self) -> None:
        async with new_client() as client:
            await self.failed_onboarding(client, "retry-ok@example.com")
            response = await client.post(RETRY_URL)
            latest = await client.get(LATEST_URL)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert [(p["disease"], p["score"], p["level"]) for p in body["predictions"]] == [
            ("DIABETES", 34, "CAUTION"),
            ("HYPERTENSION", 21, "LOW"),
        ]
        assert body["managed_diseases"] == [] and body["skipped_reason"] is None
        assert "prediction_error" not in body
        assert [p["id"] for p in latest.json()["predictions"]] == [p["id"] for p in body["predictions"]]

    async def test_retry_when_already_predicted_is_409(self) -> None:
        async with new_client() as client:
            await self.failed_onboarding(client, "retry-twice@example.com")
            await client.post(RETRY_URL)
            second = await client.post(RETRY_URL)
            user = await User.get(email="retry-twice@example.com")

        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.json() == {"detail": "이미 계산된 위험도가 있어요."}
        assert await RiskPrediction.filter(user_id=user.id).count() == 2  # 질환 2개, 쌓이지 않음

    async def test_retry_fails_again_is_503_and_saves_nothing(self) -> None:
        async with new_client() as client:
            await self.failed_onboarding(client, "retry-503@example.com")
            with patch(LOAD_MODEL_TARGET, new=broken_model):
                response = await client.post(RETRY_URL)
            user = await User.get(email="retry-503@example.com")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {"detail": "위험도를 계산하지 못했어요. 잠시 후 다시 시도해 주세요."}
        assert await RiskPrediction.filter(user_id=user.id).count() == 0

    async def test_nothing_to_predict_is_200_with_managed(self) -> None:
        async with new_client() as client:
            await self.login(client, "retry-managed@example.com")
            await client.post(
                SURVEY_URL, json=onboarding_body(is_hypertension_diagnosed=True, is_diabetes_diagnosed=True)
            )
            response = await client.post(RETRY_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "predictions": [],
            "managed_diseases": ["DIABETES", "HYPERTENSION"],
            "skipped_reason": None,
        }
