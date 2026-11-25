"""6장 건강 기록 서비스 (api.md 6-1~6-5)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from fastapi import HTTPException, status
from tortoise.transactions import in_transaction

from app.dtos.health_logs import HealthLogCreateRequest, HealthLogUpdateRequest, WeeklyLogRequest
from app.models.health_logs import HealthLog, HealthLogType
from app.models.users import User
from app.repositories.health_log_repository import HealthLogRepository
from app.services.health_log_rules import (
    KST,
    RULES,
    bad_request,
    check_daily_values,
    josa,
    kst_day_range,
    resolve_measured_at,
    week_start_at,
)

NOT_FOUND_DETAIL: Final = "기록을 찾을 수 없어요."
LOG_TYPE_FIXED_DETAIL: Final = "기록 종류는 바꿀 수 없어요. 지우고 새로 저장해 주세요."
WEEKLY_EDIT_DETAIL: Final = "주간 기록은 주간 기록 API로 고쳐 주세요."
SAME_DAY_EXISTS_DETAIL: Final = "그 날짜에는 이미 기록이 있어요. 그 기록을 고쳐 주세요."
UNKNOWN_TYPE_DETAIL: Final = "알 수 없는 기록 종류예요."
DATE_ORDER_DETAIL: Final = "시작 날짜가 끝 날짜보다 늦어요."
TOO_LONG_DETAIL: Final = "한 번에 366일까지 조회할 수 있어요."
TOO_MANY_DETAIL: Final = "기록이 너무 많아요. 기간을 줄여 주세요."
SLEEP_PAIR_DETAIL: Final = "수면 시간은 주중·주말을 함께 입력해 주세요."
MISSING_MEASURED_AT_DETAIL: Final = "측정 시각을 입력해 주세요."

MAX_RANGE_DAYS: Final = 366
MAX_ITEMS: Final = 1000

# 6-4 요청 필드 → 종류 (수면은 두 필드가 한 행)
WEEKLY_FIELD_TYPES: Final = {
    "walk_days": HealthLogType.WALK_DAYS,
    "strength_days": HealthLogType.STRENGTH_DAYS,
    "sitting_hours": HealthLogType.SITTING_HOURS,
    "breakfast": HealthLogType.BREAKFAST,
    "stress": HealthLogType.STRESS,
}
SLEEP_FIELDS: Final = ("sleep_weekday_hours", "sleep_weekend_hours")
WEEKLY_TYPES: Final = [*WEEKLY_FIELD_TYPES.values(), HealthLogType.SLEEP]


class HealthLogService:
    def __init__(self) -> None:
        self.log_repo = HealthLogRepository()

    async def create(self, user: User, data: HealthLogCreateRequest) -> tuple[dict[str, Any], bool]:
        """6-1. (응답, 새로 만들었는지). 걸음 수·컨디션은 같은 날(KST)이 있으면 덮어쓰고 False → 200."""
        check_daily_values(data.log_type, data.value, data.value2)
        measured_at = resolve_measured_at(data.measured_at, now_kst())
        values = {
            "log_type": data.log_type,
            "value": data.value,
            "value2": data.value2,
            "unit": RULES[data.log_type].unit,
            "measured_at": measured_at,
            "memo": data.memo,
        }

        async with in_transaction() as conn:
            # 같은 사용자의 하루 1행 기록을 한 줄로 세움 (동시에 두 번 눌러도 한 행)
            await User.filter(id=user.id).using_db(conn).select_for_update().first()
            if RULES[data.log_type].is_once_a_day:
                start, end = kst_day_range(measured_at.astimezone(KST).date())
                existing = await self.log_repo.find_in_range(user.id, data.log_type, start, end, using_db=conn)
                if existing is not None:
                    return serialize(await self.log_repo.update(existing, values, using_db=conn)), False
            record = await self.log_repo.create(using_db=conn, user_id=user.id, **values)
        return serialize(record), True

    async def list_logs(self, user: User, log_types: str, start_on: date, end_on: date) -> dict[str, Any]:
        """6-2. 종류 여러 개는 쉼표, 날짜는 KST 양끝 포함, 최대 366일·1000건."""
        types = parse_log_types(log_types)
        if start_on > end_on:
            raise bad_request(DATE_ORDER_DETAIL)
        if (end_on - start_on).days + 1 > MAX_RANGE_DAYS:
            raise bad_request(TOO_LONG_DETAIL)
        start, _ = kst_day_range(start_on)
        _, end = kst_day_range(end_on)
        rows = await self.log_repo.list_in_range(user.id, types, start, end, MAX_ITEMS + 1)
        if len(rows) > MAX_ITEMS:
            raise bad_request(TOO_MANY_DETAIL)
        return {"items": [serialize(row) for row in rows]}

    async def update(self, user: User, log_id: int, data: HealthLogUpdateRequest) -> dict[str, Any]:
        """6-3. 보낸 필드만, 합친 값으로 규칙 검사. 종류는 못 바꿈, 주간 기록은 6-4로."""
        record = await self.get_own(user, log_id)
        if data.log_type is not None and data.log_type != record.log_type:
            raise bad_request(LOG_TYPE_FIXED_DETAIL)
        if RULES[record.log_type].is_weekly:
            raise bad_request(WEEKLY_EDIT_DETAIL)

        changes = data.changes()
        value = changes.get("value", record.value)
        value2 = changes.get("value2", record.value2)
        if value is None:
            raise bad_request(f"{josa(RULES[record.log_type].value.label, '을', '를')} 입력해 주세요.")
        check_daily_values(record.log_type, value, value2)
        if "measured_at" in changes:
            # 수정에서 null은 "지금"이 아님: 그대로 두면 기록이 조용히 오늘로 옮겨져 지난 그래프 점이 사라짐 (#105 리뷰)
            if changes["measured_at"] is None:
                raise bad_request(MISSING_MEASURED_AT_DETAIL)
            changes["measured_at"] = resolve_measured_at(changes["measured_at"], now_kst())

        async with in_transaction() as conn:
            await User.filter(id=user.id).using_db(conn).select_for_update().first()
            if RULES[record.log_type].is_once_a_day and "measured_at" in changes:
                start, end = kst_day_range(changes["measured_at"].astimezone(KST).date())
                other = await self.log_repo.find_in_range(user.id, record.log_type, start, end, using_db=conn)
                if other is not None and other.id != record.id:
                    raise bad_request(SAME_DAY_EXISTS_DETAIL)
            record = await self.log_repo.update(record, changes, using_db=conn)
        return serialize(record)

    async def delete(self, user: User, log_id: int) -> None:
        """6-3 삭제. 주간 기록 행도 지울 수 있음 (6-5에서 null로 보임)."""
        await self.log_repo.delete(await self.get_own(user, log_id))

    async def put_weekly(self, user: User, week_start: date, data: WeeklyLogRequest) -> dict[str, Any]:
        """6-4. 보낸 항목만 그 주 1행으로 저장·덮어씀, null이면 삭제, 안 보낸 항목은 그대로."""
        measured_at = week_start_at(week_start, now_kst().date(), is_saving=True)
        sent = data.sent()
        sleep_sent = [field for field in SLEEP_FIELDS if field in sent]
        if sleep_sent:
            # 주중·주말은 한 행이라 같이 와야 함: 둘 다 값(저장) 또는 둘 다 null(삭제)
            sleep_values = [sent.get(field) for field in SLEEP_FIELDS]
            if len(sleep_sent) == 1 or (sleep_values[0] is None) != (sleep_values[1] is None):
                raise bad_request(SLEEP_PAIR_DETAIL)

        # 종류 → (value, value2) 또는 None(삭제)
        targets: dict[HealthLogType, tuple[Decimal, Decimal | None] | None] = {}
        for field, log_type in WEEKLY_FIELD_TYPES.items():
            if field in sent:
                targets[log_type] = None if sent[field] is None else (Decimal(sent[field]), None)
        if sleep_sent:
            weekday, weekend = sent[SLEEP_FIELDS[0]], sent[SLEEP_FIELDS[1]]
            targets[HealthLogType.SLEEP] = None if weekday is None else (Decimal(weekday), Decimal(weekend))

        async with in_transaction() as conn:
            await User.filter(id=user.id).using_db(conn).select_for_update().first()
            for log_type, pair in targets.items():
                existing = await self.log_repo.find_in_range(
                    user.id, log_type, measured_at, measured_at + timedelta(seconds=1), using_db=conn
                )
                if pair is None:
                    if existing is not None:
                        await self.log_repo.delete(existing, using_db=conn)
                    continue
                values = {"value": pair[0], "value2": pair[1], "unit": RULES[log_type].unit}
                if existing is not None:
                    await self.log_repo.update(existing, values, using_db=conn)
                else:
                    await self.log_repo.create(
                        using_db=conn, user_id=user.id, log_type=log_type, measured_at=measured_at, **values
                    )
        return await self.get_weekly(user, week_start)

    async def get_weekly(self, user: User, week_start: date) -> dict[str, Any]:
        """6-5. 없는 항목은 null (404 아님). 지난 주도 조회 가능."""
        measured_at = week_start_at(week_start, now_kst().date(), is_saving=False)
        rows = {row.log_type: row for row in await self.log_repo.list_at(user.id, WEEKLY_TYPES, measured_at)}
        body: dict[str, Any] = {"week_start": week_start.isoformat()}
        for field, log_type in WEEKLY_FIELD_TYPES.items():
            row = rows.get(log_type)
            body[field] = to_number(row.value) if row else None
        sleep = rows.get(HealthLogType.SLEEP)
        body["sleep_weekday_hours"] = to_number(sleep.value) if sleep else None
        body["sleep_weekend_hours"] = to_number(sleep.value2) if sleep else None
        return {key: body[key] for key in RESPONSE_ORDER}

    async def get_own(self, user: User, log_id: int) -> HealthLog:
        record = await self.log_repo.get_for_user(user.id, log_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
        return record


RESPONSE_ORDER: Final = (
    "week_start",
    "walk_days",
    "strength_days",
    "sitting_hours",
    "sleep_weekday_hours",
    "sleep_weekend_hours",
    "breakfast",
    "stress",
)


def now_kst() -> datetime:
    return datetime.now(KST)


def parse_log_types(raw: str) -> list[HealthLogType]:
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise bad_request(UNKNOWN_TYPE_DETAIL)
    try:
        return [HealthLogType(name) for name in names]
    except ValueError:
        raise bad_request(UNKNOWN_TYPE_DETAIL) from None


def to_number(value: Decimal | None) -> int | float | None:
    """DECIMAL(10,2) → 132 / 6.5 (소수가 없으면 정수로)."""
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def serialize(record: HealthLog) -> dict[str, Any]:
    return {
        "id": record.id,
        "log_type": record.log_type.value,
        "value": to_number(record.value),
        "value2": to_number(record.value2),
        "unit": record.unit,
        "measured_at": record.measured_at.astimezone(KST).isoformat(),
        "memo": record.memo,
        "created_at": record.created_at.astimezone(KST).isoformat(),
    }
