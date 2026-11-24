"""3-1 설문 저장 API (api.md 3-1, 3-1 에러 목록)."""

from datetime import date
from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.checkup_records import CheckupRecord
from app.models.health_profiles import HealthProfile
from app.models.risk_predictions import RiskPrediction
from app.models.users import User
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.survey.test_validation import make_answers, make_weekly_answers

URL = "/api/v1/health-profiles"


def onboarding_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers(**overrides)}


def weekly_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "WEEKLY", "survey_version": "v1.0", **make_weekly_answers(**overrides)}


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@patch(LOAD_MODEL_TARGET, new=fixed_model)  # 모델 파일과 상관없이 당뇨 34 / 고혈압 21
class TestCreateHealthProfileAPI(TestCase):
    async def login(self, client: AsyncClient, email: str, **signup: Any) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email, **signup))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def test_onboarding_201_fills_skipped_codes(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-201@example.com")
            response = await client.post(URL, json=onboarding_body())

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        profile = body["health_profile"]
        assert profile["kind"] == "ONBOARDING"
        assert profile["height_cm"] == 172.5
        assert profile["smoking_current"] == 8  # 피운 적 없음 → 서버가 채움
        assert profile["cigarettes_per_day"] == 888
        assert profile["created_at"].endswith("+09:00")
        assert body["managed_diseases"] == []
        assert body["skipped_reason"] is None
        assert body["prediction_error"] is False
        assert await HealthProfile.filter(id=profile["id"]).exists()
        # 테스트용 고정 모델: 당뇨 34(CAUTION) → 고혈압 21(LOW) 순서
        summary = [(p["disease"], p["method"], p["score"], p["level"]) for p in body["predictions"]]
        assert summary == [("DIABETES", "MODEL", 34, "CAUTION"), ("HYPERTENSION", "MODEL", 21, "LOW")]
        row = await RiskPrediction.get(id=body["predictions"][0]["id"])
        assert row.health_profile_id == profile["id"]
        assert row.model_version == "diabetes_risk:fixed"
        assert row.input_snapshot["inputs"]["sex"] == "MALE"
        assert row.input_snapshot["model_inputs"]["bmi"] == 26.3

    async def test_version_mismatch_409(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-version@example.com")
            response = await client.post(URL, json={**onboarding_body(), "survey_version": "v0.9"})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "detail": "설문 문항이 바뀌었어요. 다시 불러올게요.",
            "code": "SURVEY_VERSION_MISMATCH",
        }

    async def test_weekly_without_onboarding_409(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-weekly-409@example.com")
            response = await client.post(URL, json=weekly_body())

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "ONBOARDING_REQUIRED"

    async def test_onboarding_twice_409(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-twice@example.com")
            first = await client.post(URL, json=onboarding_body())
            second = await client.post(URL, json=onboarding_body())

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.json()["code"] == "ONBOARDING_ALREADY_DONE"

    async def test_version_checked_before_order(self) -> None:
        # 검사 순서: 버전 409가 순서 409보다 먼저 (프론트는 3-6부터 다시 받아야 하므로)
        async with new_client() as client:
            await self.login(client, "hp-order@example.com")
            response = await client.post(URL, json={**weekly_body(), "survey_version": "v0.9"})

        assert response.json()["code"] == "SURVEY_VERSION_MISMATCH"

    async def test_skip_violation_400_with_field(self) -> None:
        body = onboarding_body(alcohol_ever=1, alcohol_frequency=4, alcohol_amount=None, binge_frequency=None)
        async with new_client() as client:
            await self.login(client, "hp-skip@example.com")
            response = await client.post(URL, json=body)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "detail": "술을 마셔 본 적이 없으면 음주 횟수는 보낼 수 없어요.",
            "code": "SURVEY_FIELD_INVALID",
            "field": "alcohol_frequency",
        }
        assert not await HealthProfile.all().exists()

    async def test_out_of_range_422(self) -> None:
        # 형식 검사: 범위 밖·건너뛰기 코드 직접 전송·소수 둘째 자리는 FastAPI 기본 422
        async with new_client() as client:
            await self.login(client, "hp-422@example.com")
            too_short = await client.post(URL, json=onboarding_body(height_cm=99.0))
            sent_888 = await client.post(URL, json=onboarding_body(cigarettes_per_day=888))
            two_decimals = await client.post(URL, json=onboarding_body(weight_kg=78.25))

        assert too_short.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert sent_888.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert two_decimals.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_weekly_copies_previous_values(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-weekly@example.com")
            await client.post(URL, json=onboarding_body())
            response = await client.post(
                URL, json=weekly_body(height_cm=190.0, smoking_lifetime=3, smoking_current=None)
            )

        assert response.status_code == status.HTTP_201_CREATED
        profile = response.json()["health_profile"]
        assert profile["kind"] == "WEEKLY"
        assert profile["height_cm"] == 172.5  # 안 묻는 문항 → 보낸 190은 무시하고 복사
        assert profile["father_diabetes_history"] == 1
        assert profile["weight_kg"] == 76.0
        assert profile["alcohol_frequency"] == 8  # 이번엔 마셔 본 적 없음

    async def test_diagnosed_disease_is_managed(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-managed@example.com")
            response = await client.post(URL, json=onboarding_body(is_hypertension_diagnosed=True))

        assert response.json()["managed_diseases"] == ["HYPERTENSION"]
        assert [p["disease"] for p in response.json()["predictions"]] == ["DIABETES"]  # 진단받은 질환은 예측 행 없음

    async def test_pregnant_skips_prediction(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-pregnant@example.com", gender="FEMALE")
            response = await client.post(URL, json=onboarding_body(is_pregnant=True))

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["skipped_reason"] == "PREGNANT"
        assert response.json()["predictions"] == []

    async def test_male_with_pregnancy_400(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-male-preg@example.com")
            response = await client.post(URL, json=onboarding_body(is_pregnant=False))

        assert response.json()["field"] == "is_pregnant"

    async def test_age_out_of_range(self) -> None:
        async with new_client() as client:
            await self.login(client, "hp-young@example.com", birthday="2005-01-01")
            response = await client.post(URL, json=onboarding_body())

        assert response.json()["skipped_reason"] == "AGE_OUT_OF_RANGE"

    async def test_checkup_adds_criteria_rows(self) -> None:
        # 유효한 검진이 있으면 같은 질환에 MODEL + CHECKUP_CRITERIA 두 행
        email = "hp-checkup@example.com"
        async with new_client() as client:
            await self.login(client, email)
            user = await User.get(email=email)
            checkup = await CheckupRecord.create(
                user=user, checked_on=date.today(), systolic_bp=135, diastolic_bp=85, fasting_glucose=90, hba1c=5.2
            )
            response = await client.post(URL, json=onboarding_body())

        rows = [(p["disease"], p["method"], p["score"], p["level"]) for p in response.json()["predictions"]]
        assert rows == [
            ("DIABETES", "MODEL", 34, "CAUTION"),
            ("DIABETES", "CHECKUP_CRITERIA", None, "LOW"),
            ("HYPERTENSION", "MODEL", 21, "LOW"),
            ("HYPERTENSION", "CHECKUP_CRITERIA", None, "CAUTION"),
        ]
        criteria_row = await RiskPrediction.get(id=response.json()["predictions"][3]["id"])
        assert criteria_row.checkup_record_id == checkup.id
        assert criteria_row.model_version is None

    async def test_prediction_failure_keeps_survey(self) -> None:
        # 예측이 실패해도 설문은 저장하고 prediction_error: true (다시 받게 하지 않음)
        async with new_client() as client:
            await self.login(client, "hp-pred-fail@example.com")
            with patch(LOAD_MODEL_TARGET, side_effect=ValueError("모델 파일 깨짐")):
                response = await client.post(URL, json=onboarding_body())

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["prediction_error"] is True
        assert body["predictions"] == []
        assert await HealthProfile.filter(id=body["health_profile"]["id"]).exists()
        assert not await RiskPrediction.all().exists()
