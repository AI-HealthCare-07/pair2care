"""5-2 최근 예측·5-3 예측 상세 API."""

from datetime import date, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.checkup_records import CheckupRecord
from app.models.users import User
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.survey.test_validation import make_answers

LATEST_URL = "/api/v1/risk-predictions/latest"
SURVEY_URL = "/api/v1/health-profiles"


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def onboarding_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers(**overrides)}


def weekly_same_habits(weight_kg: float) -> dict[str, Any]:
    """몸무게만 바꾸고 나머지 습관은 가입 설문과 같은 주간 설문 (술 마심·비흡연)."""
    return {
        "kind": "WEEKLY",
        "survey_version": "v1.0",
        "weight_kg": weight_kg,
        "waist_cm": None,
        "alcohol_ever": 2,
        "alcohol_frequency": 5,
        "alcohol_amount": 3,
        "binge_frequency": None,  # 직전에도 해당 → 안 물음, 복사
        "smoking_lifetime": 3,
        "smoking_current": None,
        "cigarettes_per_day": None,
        "is_hypertension_diagnosed": False,
        "is_diabetes_diagnosed": False,
        "is_pregnant": None,
    }


class TestRiskPredictionAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def test_latest_without_survey_is_404(self) -> None:
        async with new_client() as client:
            await self.login(client, "rp-404@example.com")
            response = await client.get(LATEST_URL)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "아직 설문 기록이 없어요."}

    async def test_latest_after_onboarding(self) -> None:
        async with new_client() as client:
            await self.login(client, "rp-latest@example.com")
            created = await client.post(SURVEY_URL, json=onboarding_body(is_hypertension_diagnosed=True))
            response = await client.get(LATEST_URL)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["health_profile_id"] == created.json()["health_profile"]["id"]
        assert [(p["disease"], p["score"]) for p in body["predictions"]] == [("DIABETES", 34)]
        assert "checkup_record_id" not in body["predictions"][0]
        assert body["managed_diseases"] == ["HYPERTENSION"]
        assert body["skipped_reason"] is None
        assert body["metabolic_syndrome"] is None  # 검진 없음

    async def test_latest_with_checkup_has_criteria_and_metabolic(self) -> None:
        email = "rp-checkup@example.com"
        async with new_client() as client:
            await self.login(client, email)
            user = await User.get(email=email)
            checkup = await CheckupRecord.create(
                user=user, checked_on=date.today(), systolic_bp=135, diastolic_bp=85, waist_cm=95
            )
            await client.post(SURVEY_URL, json=onboarding_body())
            response = await client.get(LATEST_URL)

        body = response.json()
        methods = [(p["disease"], p["method"]) for p in body["predictions"]]
        assert methods == [("DIABETES", "MODEL"), ("HYPERTENSION", "MODEL"), ("HYPERTENSION", "CHECKUP_CRITERIA")]
        assert body["predictions"][2]["checkup_record_id"] == checkup.id
        # 허리·혈압 해당 2개, 중성지방·HDL·혈당 모름 → UNKNOWN
        assert body["metabolic_syndrome"] == {
            "status": "UNKNOWN",
            "met_count": 2,
            "missing": ["triglyceride", "hdl_cholesterol", "fasting_glucose"],
        }

    async def test_detail_compares_with_previous_model_row(self) -> None:
        async with new_client() as client:
            await self.login(client, "rp-detail@example.com")
            first = await client.post(SURVEY_URL, json=onboarding_body())
            second = await client.post(SURVEY_URL, json=weekly_same_habits(76.0))
            new_id = second.json()["predictions"][0]["id"]
            response = await client.get(f"/api/v1/risk-predictions/{new_id}")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["disease"] == "DIABETES"
        assert body["model_version"] == "diabetes_risk:dummy"
        assert body["factors"] == []  # 가짜 모델은 계수가 0
        assert body["changed_inputs"] == [{"feature": "weight_kg", "before": 78.2, "after": 76.0}]
        assert body["previous"]["id"] == first.json()["predictions"][0]["id"]
        assert body["previous"]["score"] == 34

    async def test_first_detail_has_no_previous(self) -> None:
        async with new_client() as client:
            await self.login(client, "rp-first@example.com")
            created = await client.post(SURVEY_URL, json=onboarding_body())
            response = await client.get(f"/api/v1/risk-predictions/{created.json()['predictions'][0]['id']}")

        assert response.json()["previous"] is None
        assert response.json()["changed_inputs"] is None

    async def test_criteria_detail_shows_used_values(self) -> None:
        email = "rp-criteria@example.com"
        async with new_client() as client:
            await self.login(client, email)
            user = await User.get(email=email)
            checked_on = date.today() - timedelta(days=30)  # 1년 안이라 유효
            await CheckupRecord.create(user=user, checked_on=checked_on, fasting_glucose=108, hba1c=5.5)
            created = await client.post(SURVEY_URL, json=onboarding_body())
            criteria_id = created.json()["predictions"][1]["id"]
            response = await client.get(f"/api/v1/risk-predictions/{criteria_id}")

        body = response.json()
        assert body["method"] == "CHECKUP_CRITERIA"
        assert body["score"] is None
        assert body["used_values"] == {"fasting_glucose": 108, "hba1c": 5.5}
        assert body["checked_on"] == checked_on.isoformat()
        assert body["factors"] is None and body["changed_inputs"] is None and body["previous"] is None

    async def test_other_users_prediction_is_404(self) -> None:
        async with new_client() as owner:
            await self.login(owner, "rp-owner@example.com")
            created = await owner.post(SURVEY_URL, json=onboarding_body())
        prediction_id = created.json()["predictions"][0]["id"]

        async with new_client() as other:
            await self.login(other, "rp-other@example.com")
            response = await other.get(f"/api/v1/risk-predictions/{prediction_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
