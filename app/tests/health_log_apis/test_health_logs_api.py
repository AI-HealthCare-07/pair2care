"""6장 건강 기록 API (api.md 6-1~6-5)."""

from datetime import date, datetime, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.health_logs import HealthLog
from app.services.health_log_rules import KST
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data

URL = "/api/v1/health-logs"


def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def kst_now() -> datetime:
    return datetime.now(KST)


def at(days_ago: int, hour: int = 8) -> str:
    """KST n일 전 hh:00 (ISO, +09:00)."""
    day = kst_now().date() - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, hour, tzinfo=KST).isoformat()


def this_monday() -> date:
    today = kst_now().date()
    return today - timedelta(days=today.weekday())


class TestHealthLogsAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def post(self, client: AsyncClient, **body: Any) -> Any:
        return await client.post(URL, json=body)

    # ---------- 6-1 ----------

    async def test_create_blood_pressure(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-bp@example.com")
            response = await self.post(
                client,
                log_type="BLOOD_PRESSURE",
                value=132,
                value2=84,
                measured_at=at(1, 7),
                memo="아침 약 먹기 전",
                unit="cmHg",  # 클라이언트 unit은 무시
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert (body["value"], body["value2"], body["unit"], body["memo"]) == (132, 84, "mmHg", "아침 약 먹기 전")
        assert body["measured_at"].endswith("+09:00")

    async def test_measured_at_defaults_to_now_and_decimal_kept(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-weight@example.com")
            response = await self.post(client, log_type="WEIGHT", value=70.4)

        assert response.json()["value"] == 70.4
        assert response.json()["unit"] == "kg"

    async def test_rule_violations_are_400(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-400@example.com")
            weekly = await self.post(client, log_type="WALK_DAYS", value=3)
            future = await self.post(
                client, log_type="WEIGHT", value=70, measured_at=(kst_now() + timedelta(hours=1)).isoformat()
            )
            pressure = await self.post(client, log_type="BLOOD_PRESSURE", value=80, value2=90)
            decimals = await self.post(client, log_type="WEIGHT", value=70.25)

        assert weekly.json() == {"detail": "주간 기록은 주간 기록 API로 저장해 주세요."}
        assert future.json() == {"detail": "아직 오지 않은 시각으로는 기록할 수 없어요."}
        assert pressure.json() == {"detail": "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."}
        assert decimals.json() == {"detail": "체중은 소수 첫째 자리까지 입력해 주세요."}
        assert not await HealthLog.all().exists()

    async def test_steps_same_day_overwrites_with_200(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-steps@example.com")
            first = await self.post(client, log_type="STEPS", value=4000, measured_at=at(1, 9))
            second = await self.post(client, log_type="STEPS", value=8500, measured_at=at(1, 21))
            other_day = await self.post(client, log_type="STEPS", value=3000, measured_at=at(2, 21))

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["value"] == 8500
        assert other_day.status_code == status.HTTP_201_CREATED
        assert await HealthLog.filter(log_type="STEPS").count() == 2

    async def test_blood_pressure_many_times_a_day(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-bp-many@example.com")
            for hour in (7, 12, 21):
                response = await self.post(
                    client, log_type="BLOOD_PRESSURE", value=130, value2=80, measured_at=at(1, hour)
                )
                assert response.status_code == status.HTTP_201_CREATED

        assert await HealthLog.filter(log_type="BLOOD_PRESSURE").count() == 3

    # ---------- 6-2 ----------

    async def test_list_by_types_and_kst_dates_ascending(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-list@example.com")
            await self.post(client, log_type="WEIGHT", value=71, measured_at=at(2, 8))
            await self.post(client, log_type="BLOOD_PRESSURE", value=130, value2=80, measured_at=at(3, 8))
            await self.post(client, log_type="BLOOD_GLUCOSE", value=100, measured_at=at(2, 8))
            await self.post(client, log_type="WEIGHT", value=72, measured_at=at(10, 8))  # 기간 밖
            today = kst_now().date()
            response = await client.get(
                URL,
                params={"log_type": "BLOOD_PRESSURE,WEIGHT", "from": str(today - timedelta(days=5)), "to": str(today)},
            )

        items = response.json()["items"]
        assert [(item["log_type"], item["value"]) for item in items] == [("BLOOD_PRESSURE", 130), ("WEIGHT", 71)]

    async def test_list_validation(self) -> None:
        today = kst_now().date()
        async with new_client() as client:
            await self.login(client, "hl-list-400@example.com")
            unknown = await client.get(URL, params={"log_type": "SLEEPING", "from": str(today), "to": str(today)})
            reversed_ = await client.get(
                URL, params={"log_type": "WEIGHT", "from": str(today), "to": str(today - timedelta(days=1))}
            )
            too_long = await client.get(
                URL, params={"log_type": "WEIGHT", "from": str(today - timedelta(days=366)), "to": str(today)}
            )
            missing = await client.get(URL, params={"log_type": "WEIGHT"})

        assert unknown.json() == {"detail": "알 수 없는 기록 종류예요."}
        assert reversed_.json() == {"detail": "시작 날짜가 끝 날짜보다 늦어요."}
        assert too_long.json() == {"detail": "한 번에 366일까지 조회할 수 있어요."}
        assert missing.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ---------- 6-3 ----------

    async def test_update_and_delete(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-update@example.com")
            created = await self.post(client, log_type="BLOOD_PRESSURE", value=140, value2=90, measured_at=at(1, 7))
            log_id = created.json()["id"]
            updated = await client.patch(f"{URL}/{log_id}", json={"value": 135, "memo": None})
            bad = await client.patch(f"{URL}/{log_id}", json={"value2": 140})
            type_change = await client.patch(f"{URL}/{log_id}", json={"log_type": "WEIGHT"})
            deleted = await client.delete(f"{URL}/{log_id}")

        assert updated.status_code == status.HTTP_200_OK
        assert (updated.json()["value"], updated.json()["value2"], updated.json()["memo"]) == (135, 90, None)
        assert bad.json() == {"detail": "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."}
        assert type_change.json() == {"detail": "기록 종류는 바꿀 수 없어요. 지우고 새로 저장해 주세요."}
        assert deleted.status_code == status.HTTP_204_NO_CONTENT
        assert not await HealthLog.filter(id=log_id).exists()

    async def test_steps_cannot_move_onto_another_day_with_steps(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-move@example.com")
            await self.post(client, log_type="STEPS", value=5000, measured_at=at(1, 9))
            yesterday = await self.post(client, log_type="STEPS", value=3000, measured_at=at(2, 9))
            response = await client.patch(f"{URL}/{yesterday.json()['id']}", json={"measured_at": at(1, 20)})

        assert response.json() == {"detail": "그 날짜에는 이미 기록이 있어요. 그 기록을 고쳐 주세요."}

    async def test_weekly_row_cannot_be_patched(self) -> None:
        async with new_client() as client:
            await self.login(client, "hl-weekly-patch@example.com")
            await client.put(f"{URL}/weekly/{this_monday()}", json={"walk_days": 3})
            row = await HealthLog.get(log_type="WALK_DAYS")
            response = await client.patch(f"{URL}/{row.id}", json={"value": 4})

        assert response.json() == {"detail": "주간 기록은 주간 기록 API로 고쳐 주세요."}

    async def test_others_log_is_404(self) -> None:
        async with new_client() as owner:
            await self.login(owner, "hl-owner@example.com")
            created = await self.post(owner, log_type="WEIGHT", value=70)
        async with new_client() as other:
            await self.login(other, "hl-other@example.com")
            patch_ = await other.patch(f"{URL}/{created.json()['id']}", json={"value": 71})
            delete = await other.delete(f"{URL}/{created.json()['id']}")

        assert patch_.status_code == delete.status_code == status.HTTP_404_NOT_FOUND
        assert patch_.json() == {"detail": "기록을 찾을 수 없어요."}

    # ---------- 6-4·6-5 ----------

    async def test_weekly_put_only_sent_fields_and_get(self) -> None:
        monday = this_monday()
        async with new_client() as client:
            await self.login(client, "hl-weekly@example.com")
            first = await client.put(
                f"{URL}/weekly/{monday}",
                json={"walk_days": 3, "sitting_hours": 9, "sleep_weekday_hours": 6.5, "sleep_weekend_hours": 8},
            )
            second = await client.put(
                f"{URL}/weekly/{monday}", json={"walk_days": 4, "stress": 1, "sitting_hours": None}
            )
            fetched = await client.get(f"{URL}/weekly/{monday}")

        assert first.status_code == status.HTTP_200_OK
        assert (
            second.json()
            == fetched.json()
            == {
                "week_start": str(monday),
                "walk_days": 4,  # 덮어씀
                "strength_days": None,
                "sitting_hours": None,  # null → 삭제
                "sleep_weekday_hours": 6.5,  # 안 보냄 → 그대로
                "sleep_weekend_hours": 8,
                "breakfast": None,
                "stress": 1,
            }
        )
        assert await HealthLog.filter(log_type="WALK_DAYS").count() == 1  # 한 주 1행

    async def test_weekly_rules(self) -> None:
        monday = this_monday()
        async with new_client() as client:
            await self.login(client, "hl-weekly-400@example.com")
            one_side = await client.put(f"{URL}/weekly/{monday}", json={"sleep_weekday_hours": 7})
            mixed = await client.put(
                f"{URL}/weekly/{monday}", json={"sleep_weekday_hours": 7, "sleep_weekend_hours": None}
            )
            not_monday = await client.put(f"{URL}/weekly/{monday + timedelta(days=1)}", json={"walk_days": 3})
            too_old = await client.put(f"{URL}/weekly/{monday - timedelta(days=14)}", json={"walk_days": 3})
            last_week = await client.put(f"{URL}/weekly/{monday - timedelta(days=7)}", json={"walk_days": 2})
            out_of_range = await client.put(f"{URL}/weekly/{monday}", json={"walk_days": 8})
            old_get = await client.get(f"{URL}/weekly/{monday - timedelta(days=14)}")

        assert one_side.json() == mixed.json() == {"detail": "수면 시간은 주중·주말을 함께 입력해 주세요."}
        assert not_monday.json() == {"detail": "주간 기록은 그 주 월요일 날짜로 보내 주세요."}
        assert too_old.json() == {"detail": "주간 기록은 이번 주와 지난주만 저장할 수 있어요."}
        assert last_week.status_code == status.HTTP_200_OK
        assert out_of_range.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert old_get.status_code == status.HTTP_200_OK  # 조회는 지난 주도 됨, 없으면 null
        assert old_get.json()["walk_days"] is None

    async def test_weekly_sleep_both_null_deletes(self) -> None:
        monday = this_monday()
        async with new_client() as client:
            await self.login(client, "hl-sleep-del@example.com")
            await client.put(f"{URL}/weekly/{monday}", json={"sleep_weekday_hours": 6, "sleep_weekend_hours": 9})
            response = await client.put(
                f"{URL}/weekly/{monday}", json={"sleep_weekday_hours": None, "sleep_weekend_hours": None}
            )

        assert (response.json()["sleep_weekday_hours"], response.json()["sleep_weekend_hours"]) == (None, None)
        assert not await HealthLog.filter(log_type="SLEEP").exists()
