"""4장 검진 수치 API (api.md 4-1~4-5)."""

from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.checkup_records import CheckupRecord
from app.models.risk_predictions import RiskPrediction
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.prediction.fixed_models import LOAD_MODEL_TARGET, fixed_model
from app.tests.prediction_apis.test_risk_prediction_api import weekly_same_habits
from app.tests.survey.test_validation import make_answers

URL = "/api/v1/checkup-records"
SURVEY_URL = "/api/v1/health-profiles"
LATEST_URL = "/api/v1/risk-predictions/latest"


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def onboarding_body(**overrides: Any) -> dict[str, Any]:
    return {"kind": "ONBOARDING", "survey_version": "v1.0", **make_answers(**overrides)}


def checkup_body(**overrides: Any) -> dict[str, Any]:
    """api.md 4-1 예시 (혈압 134/86 → 고혈압 주의, 공복혈당 108·당화혈색소 5.8 → 당뇨 주의)."""
    body: dict[str, Any] = {
        "checked_on": (date.today() - timedelta(days=30)).isoformat(),
        "systolic_bp": 134,
        "diastolic_bp": 86,
        "fasting_glucose": 108,
        "waist_cm": 91.0,
        "triglyceride": 162,
        "hdl_cholesterol": 44,
        "hba1c": 5.8,
    }
    body.update(overrides)
    return body


@patch(LOAD_MODEL_TARGET, new=fixed_model)  # 모델 파일과 상관없이 당뇨 34 / 고혈압 21
class TestCheckupRecordsAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def test_create_without_survey_saves_only_record(self) -> None:
        # 설문이 없으면 예측 안 함 → 나중에 3-1이 이 검진을 읽어 같이 판정
        async with new_client() as client:
            await self.login(client, "ck-no-survey@example.com")
            response = await client.post(URL, json=checkup_body())

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["checkup_record"]["systolic_bp"] == 134
        assert body["checkup_record"]["waist_cm"] == 91.0
        assert body["checkup_record"]["source"] == "MANUAL"
        assert body["predictions"] == []
        assert body["prediction_error"] is False
        assert not await RiskPrediction.all().exists()

    async def test_survey_then_checkup_shows_criteria_in_latest(self) -> None:
        # 설문 → 검진 순서: 검진 저장으로 생긴 기준표 행이 최근 설문에 붙어 5-2에 보임 (#97 리뷰 약속)
        async with new_client() as client:
            await self.login(client, "ck-order@example.com")
            survey = await client.post(SURVEY_URL, json=onboarding_body())
            created = await client.post(URL, json=checkup_body())
            latest = await client.get(LATEST_URL)

        rows = [(p["disease"], p["method"], p["level"]) for p in created.json()["predictions"]]
        assert rows == [
            ("DIABETES", "MODEL", "CAUTION"),
            ("DIABETES", "CHECKUP_CRITERIA", "CAUTION"),
            ("HYPERTENSION", "MODEL", "LOW"),
            ("HYPERTENSION", "CHECKUP_CRITERIA", "CAUTION"),
        ]
        body = latest.json()
        assert body["health_profile_id"] == survey.json()["health_profile"]["id"]
        criteria = [p for p in body["predictions"] if p["method"] == "CHECKUP_CRITERIA"]
        assert {p["checkup_record_id"] for p in criteria} == {created.json()["checkup_record"]["id"]}
        assert body["metabolic_syndrome"]["status"] in {"MET", "NOT_MET", "UNKNOWN"}

    async def test_detail_previous_skips_same_survey_rows(self) -> None:
        # 검진 저장으로 같은 설문에 MODEL 행이 또 생겨도, 5-3 비교는 지난 설문과 함
        async with new_client() as client:
            await self.login(client, "ck-previous@example.com")
            first = await client.post(SURVEY_URL, json=onboarding_body())
            await client.post(SURVEY_URL, json=weekly_same_habits(76.0))
            created = await client.post(URL, json=checkup_body())
            newest_model_id = created.json()["predictions"][0]["id"]
            detail = await client.get(f"/api/v1/risk-predictions/{newest_model_id}")

        body = detail.json()
        assert body["previous"]["id"] == first.json()["predictions"][0]["id"]
        assert body["changed_inputs"] == [{"feature": "weight_kg", "before": 78.2, "after": 76.0}]

    async def test_rule_violations_are_400(self) -> None:
        async with new_client() as client:
            await self.login(client, "ck-400@example.com")
            future = await client.post(
                URL, json=checkup_body(checked_on=(date.today() + timedelta(days=1)).isoformat())
            )
            pressure = await client.post(URL, json=checkup_body(systolic_bp=80, diastolic_bp=90))
            empty = await client.post(URL, json={"checked_on": date.today().isoformat()})

        assert future.json() == {"detail": "검진 날짜는 오늘 이후로 입력할 수 없어요."}
        assert pressure.json() == {"detail": "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."}
        assert empty.status_code == status.HTTP_400_BAD_REQUEST
        assert empty.json() == {"detail": "검진 수치를 하나 이상 입력해 주세요."}
        assert not await CheckupRecord.all().exists()

    async def test_out_of_range_is_422(self) -> None:
        async with new_client() as client:
            await self.login(client, "ck-422@example.com")
            response = await client.post(URL, json=checkup_body(systolic_bp=300))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_list_newest_checked_on_first_with_cursor(self) -> None:
        today = date.today()
        async with new_client() as client:
            await self.login(client, "ck-list@example.com")
            # 넣는 순서와 검진 날짜 순서를 다르게
            for days_ago in (10, 300, 100):
                await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=days_ago)).isoformat()))
            first_page = await client.get(URL, params={"limit": 2})
            second_page = await client.get(URL, params={"limit": 2, "cursor": first_page.json()["next_cursor"]})

        dates = [item["checked_on"] for item in first_page.json()["items"] + second_page.json()["items"]]
        expected = [(today - timedelta(days=d)).isoformat() for d in (10, 100, 300)]
        assert dates == expected
        assert first_page.json()["next_cursor"] is not None
        assert second_page.json()["next_cursor"] is None

    async def test_others_record_is_404(self) -> None:
        async with new_client() as owner:
            await self.login(owner, "ck-owner@example.com")
            created = await owner.post(URL, json=checkup_body())
        record_id = created.json()["checkup_record"]["id"]

        async with new_client() as other:
            await self.login(other, "ck-other@example.com")
            get = await other.get(f"{URL}/{record_id}")
            patch_ = await other.patch(f"{URL}/{record_id}", json={"hba1c": 6.0})
            delete = await other.delete(f"{URL}/{record_id}")
            cursor = await other.get(URL, params={"cursor": record_id})

        assert get.status_code == patch_.status_code == delete.status_code == cursor.status_code == 404
        assert get.json() == {"detail": "검진 기록을 찾을 수 없어요."}

    async def test_update_only_sent_fields_and_repredict_latest(self) -> None:
        async with new_client() as client:
            await self.login(client, "ck-update@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            created = await client.post(URL, json=checkup_body())
            record_id = created.json()["checkup_record"]["id"]
            rows_before = await RiskPrediction.all().count()
            response = await client.patch(f"{URL}/{record_id}", json={"systolic_bp": 150, "hba1c": None})

        assert response.status_code == status.HTTP_200_OK
        record = response.json()["checkup_record"]
        assert (record["systolic_bp"], record["diastolic_bp"], record["hba1c"]) == (150, 86, None)
        # 가장 최근 검진이라 다시 예측 → 행이 늘어나고, 지난 행은 그대로
        assert response.json()["predictions"]
        assert await RiskPrediction.all().count() > rows_before

    async def test_update_older_record_does_not_repredict(self) -> None:
        today = date.today()
        async with new_client() as client:
            await self.login(client, "ck-update-old@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            old = await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=300)).isoformat()))
            await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=10)).isoformat()))
            rows_before = await RiskPrediction.all().count()
            response = await client.patch(f"{URL}/{old.json()['checkup_record']['id']}", json={"waist_cm": 88.5})

        assert response.json()["checkup_record"]["waist_cm"] == 88.5
        assert response.json()["predictions"] == []
        assert await RiskPrediction.all().count() == rows_before

    async def test_update_cannot_remove_every_value(self) -> None:
        async with new_client() as client:
            await self.login(client, "ck-update-empty@example.com")
            created = await client.post(URL, json={"checked_on": date.today().isoformat(), "hba1c": 5.5})
            response = await client.patch(f"{URL}/{created.json()['checkup_record']['id']}", json={"hba1c": None})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "검진 수치를 하나 이상 입력해 주세요."}

    async def test_delete_keeps_prediction_history(self) -> None:
        async with new_client() as client:
            await self.login(client, "ck-delete@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            created = await client.post(URL, json=checkup_body())
            record_id = created.json()["checkup_record"]["id"]
            criteria_id = created.json()["predictions"][1]["id"]
            response = await client.delete(f"{URL}/{record_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await CheckupRecord.filter(id=record_id).exists()
        criteria = await RiskPrediction.get(id=criteria_id)
        assert criteria.checkup_record_id is None  # FK SET NULL, 판정 당시 수치는 input_snapshot에 남음
        assert criteria.input_snapshot["fasting_glucose"] == 108  # 당뇨 기준표 행

    async def test_source_is_always_manual(self) -> None:
        # 4-6 결과지 인식 전까지 클라이언트가 OCR을 보내도 MANUAL (#103 리뷰)
        async with new_client() as client:
            await self.login(client, "ck-source@example.com")
            response = await client.post(URL, json=checkup_body(source="OCR"))

        assert response.json()["checkup_record"]["source"] == "MANUAL"

    async def test_moving_latest_record_older_repredicts_with_new_latest(self) -> None:
        # 가장 최근 검진의 날짜를 예전으로 옮기면 다른 기록이 최근 → 그 기록으로 다시 판정 (#103 리뷰)
        today = date.today()
        async with new_client() as client:
            await self.login(client, "ck-move-latest@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            other = await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=60)).isoformat()))
            latest = await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=10)).isoformat()))
            response = await client.patch(
                f"{URL}/{latest.json()['checkup_record']['id']}",
                json={"checked_on": (today - timedelta(days=200)).isoformat()},
            )
            latest_view = await client.get(LATEST_URL)

        assert response.json()["predictions"]  # 수정 전엔 최근이었으니 다시 예측
        criteria_ids = {
            p["checkup_record_id"] for p in latest_view.json()["predictions"] if p["method"] == "CHECKUP_CRITERIA"
        }
        assert criteria_ids == {other.json()["checkup_record"]["id"]}

    async def test_deleting_latest_repredicts_with_remaining_record(self) -> None:
        today = date.today()
        async with new_client() as client:
            await self.login(client, "ck-delete-latest@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            remaining = await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=60)).isoformat()))
            latest = await client.post(URL, json=checkup_body(checked_on=(today - timedelta(days=10)).isoformat()))
            await client.delete(f"{URL}/{latest.json()['checkup_record']['id']}")
            latest_view = await client.get(LATEST_URL)

        criteria_ids = {
            p["checkup_record_id"] for p in latest_view.json()["predictions"] if p["method"] == "CHECKUP_CRITERIA"
        }
        assert criteria_ids == {remaining.json()["checkup_record"]["id"]}

    async def test_deleting_only_record_hides_old_criteria(self) -> None:
        # 남은 검진이 없으면 기준표 없이 다시 예측 → 지운 검진의 판정은 5-2에 안 보임 (#103 리뷰)
        async with new_client() as client:
            await self.login(client, "ck-delete-only@example.com")
            await client.post(SURVEY_URL, json=onboarding_body())
            created = await client.post(URL, json=checkup_body())
            await client.delete(f"{URL}/{created.json()['checkup_record']['id']}")
            latest_view = await client.get(LATEST_URL)

        methods = [p["method"] for p in latest_view.json()["predictions"]]
        assert methods == ["MODEL", "MODEL"]
        assert latest_view.json()["metabolic_syndrome"] is None
