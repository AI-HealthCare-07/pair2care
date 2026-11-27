"""7장 대시보드 API (api.md 7-1~7-3)."""

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.services.health_log_rules import KST
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.survey.test_validation import make_answers

URL = "/api/v1/dashboard"
SURVEY_URL = "/api/v1/health-profiles"
LOGS_URL = "/api/v1/health-logs"


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def onboarding_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers(**overrides)}


def today_kst() -> date:
    return datetime.now(KST).date()


def this_monday() -> date:
    return today_kst() - timedelta(days=today_kst().weekday())


def at(day: date, hour: int) -> str:
    return datetime(day.year, day.month, day.day, hour, tzinfo=KST).isoformat()


@patch(LOAD_MODEL_TARGET, new=fixed_model)  # 모델 파일과 상관없이 당뇨 34 / 고혈압 21
class TestDashboardAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    # ---------- 7-1 ----------

    async def test_risk_trend_this_week(self) -> None:
        async with new_client() as client:
            await self.login(client, "db-trend@example.com")
            survey = await client.post(SURVEY_URL, json=onboarding_body())
            response = await client.get(f"{URL}/risk-trend")

        assert response.status_code == status.HTTP_200_OK
        diabetes, hypertension = response.json()["series"]
        assert diabetes["disease"] == "DIABETES" and diabetes["managed"] is False
        assert diabetes["points"] == [
            {
                "week_start": this_monday().isoformat(),
                "score": 34,
                "level": "CAUTION",
                "prediction_id": survey.json()["predictions"][0]["id"],
                "criteria_level": None,
                "survey_kind": "ONBOARDING",
            }
        ]
        assert hypertension["points"][0]["score"] == 21

    async def test_risk_trend_edit_point_has_survey_kind_edit(self) -> None:
        async with new_client() as client:
            await self.login(client, "db-trend-edit@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            edited = await client.post(SURVEY_URL, json={**onboarding_body(height_cm=180.0), "kind": "EDIT"})
            response = await client.get(f"{URL}/risk-trend")

        # 같은 주에 고치면 그 주의 점은 마지막(EDIT) 예측 → 화면이 "수정"으로 표시 (3-4)
        point = response.json()["series"][0]["points"][0]
        assert point["prediction_id"] == edited.json()["predictions"][0]["id"]
        assert point["survey_kind"] == "EDIT"

    async def test_risk_trend_managed_and_empty(self) -> None:
        async with new_client() as client:
            await self.login(client, "db-trend-managed@example.com")
            empty = await client.get(f"{URL}/risk-trend")
            await client.post(SURVEY_URL, json=onboarding_body(is_hypertension_diagnosed=True))
            managed = await client.get(f"{URL}/risk-trend")
            too_many = await client.get(f"{URL}/risk-trend", params={"weeks": 53})

        # 설문 전에도 200 + 두 질환 빈 추이 (화면은 "아직 기록이 없어요")
        assert [s["points"] for s in empty.json()["series"]] == [[], []]
        assert managed.json()["series"][1] == {"disease": "HYPERTENSION", "managed": True, "points": []}
        assert too_many.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ---------- 7-2 ----------

    async def test_logs_day_bucket_averages_blood_pressure(self) -> None:
        yesterday = today_kst() - timedelta(days=1)
        async with new_client() as client:
            await self.login(client, "db-logs@example.com")
            for value, value2, hour in ((130, 82, 7), (133, 84, 21)):
                await client.post(
                    LOGS_URL,
                    json={
                        "log_type": "BLOOD_PRESSURE",
                        "value": value,
                        "value2": value2,
                        "measured_at": at(yesterday, hour),
                    },
                )
            response = await client.get(
                f"{URL}/logs",
                params={"log_type": "BLOOD_PRESSURE", "from": str(yesterday), "to": str(today_kst()), "bucket": "day"},
            )

        assert response.json() == {
            "log_type": "BLOOD_PRESSURE",
            "unit": "mmHg",
            "bucket": "day",
            "points": [{"date": yesterday.isoformat(), "value": 131.5, "value2": 83.0, "count": 2}],
        }

    async def test_logs_validation(self) -> None:
        today = str(today_kst())
        async with new_client() as client:
            await self.login(client, "db-logs-400@example.com")
            weekly = await client.get(f"{URL}/logs", params={"log_type": "SLEEP", "from": today, "to": today})
            unknown = await client.get(f"{URL}/logs", params={"log_type": "PULSE", "from": today, "to": today})
            bad_bucket = await client.get(
                f"{URL}/logs", params={"log_type": "WEIGHT", "from": today, "to": today, "bucket": "month"}
            )

        assert weekly.json() == {"detail": "주간 기록은 주간 기록 API로 조회해 주세요."}
        assert unknown.json() == {"detail": "알 수 없는 기록 종류예요."}
        assert bad_bucket.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ---------- 7-3 ----------

    async def test_summary_this_week(self) -> None:
        monday = this_monday()
        yesterday = today_kst() - timedelta(days=1)
        async with new_client() as client:
            await self.login(client, "db-summary@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            if yesterday >= monday:  # 월요일에 돌리면 어제는 지난주
                await client.post(LOGS_URL, json={"log_type": "STEPS", "value": 6000, "measured_at": at(yesterday, 21)})
            await client.post(LOGS_URL, json={"log_type": "WEIGHT", "value": 70.4})
            await client.put(f"{LOGS_URL}/weekly/{monday}", json={"walk_days": 3})
            response = await client.get(f"{URL}/summary")

        body = response.json()
        assert body["week_start"] == monday.isoformat()
        assert body["priority_disease"] == "DIABETES"  # 34 CAUTION > 21 LOW
        assert [(r["disease"], r["score"], r["level"]) for r in body["latest_risk"]] == [
            ("DIABETES", 34, "CAUTION"),
            ("HYPERTENSION", 21, "LOW"),
        ]
        assert body["logs"]["WEIGHT"]["avg_value"] == 70.4
        assert "WALK_DAYS" not in body["logs"]  # 주간 기록은 weekly_record_done으로만
        assert body["weekly_record_done"] is True
        assert body["challenge"] is None and body["meal"] is None

    async def test_summary_before_survey_and_managed(self) -> None:
        async with new_client() as client:
            await self.login(client, "db-summary-empty@example.com")
            empty = await client.get(f"{URL}/summary")
            await client.post(SURVEY_URL, json=onboarding_body(is_diabetes_diagnosed=True))
            managed = await client.get(f"{URL}/summary")
            not_monday = await client.get(
                f"{URL}/summary", params={"week_start": str(this_monday() + timedelta(days=1))}
            )

        assert empty.status_code == status.HTTP_200_OK
        assert (empty.json()["priority_disease"], empty.json()["latest_risk"], empty.json()["logs"]) == (None, [], {})
        assert empty.json()["weekly_record_done"] is False
        # 관리 중이면 그 질환 먼저 (진단받은 당뇨는 예측 행이 없어도)
        assert managed.json()["priority_disease"] == "DIABETES"
        assert managed.json()["managed_diseases"] == ["DIABETES"]
        assert [r["disease"] for r in managed.json()["latest_risk"]] == ["HYPERTENSION"]
        assert not_monday.json() == {"detail": "week_start는 그 주 월요일 날짜로 보내 주세요."}
