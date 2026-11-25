"""4장 검진 수치 서비스 (api.md 4-1~4-5)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.dtos.checkup_records import CheckupRecordCreateRequest, CheckupRecordUpdateRequest
from app.models.checkup_records import CheckupRecord, CheckupSource
from app.models.users import User
from app.repositories.checkup_record_repository import CheckupRecordRepository
from app.services.checkup_rules import CHECKUP_VALUE_FIELDS, check_checkup_values
from app.services.prediction.service import PredictionService

KST = ZoneInfo("Asia/Seoul")
NOT_FOUND_DETAIL: Final = "검진 기록을 찾을 수 없어요."
DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 50


class CheckupRecordService:
    def __init__(self) -> None:
        self.checkup_repo = CheckupRecordRepository()
        self.prediction_service = PredictionService()

    async def create(self, user: User, data: CheckupRecordCreateRequest) -> dict[str, Any]:
        """4-1. 저장 → 최근 설문으로 다시 예측 (기준표 판정 행이 이 검진으로 생김)."""
        values = data.model_dump() | {"source": CheckupSource.MANUAL}  # 4-6 결과지 인식 전까지 직접 입력만
        check_checkup_values(values, today_kst())
        record = await self.checkup_repo.create(user.id, values)
        return {"checkup_record": serialize(record), **await self.prediction_service.repredict_latest(user)}

    async def list_records(self, user: User, limit: int, cursor_id: int | None) -> dict[str, Any]:
        """4-2. 커서는 마지막 id. 내 기록이 아니거나 없는 id면 처음부터가 아니라 404 (잘못된 커서를 드러냄)."""
        cursor = None
        if cursor_id is not None:
            cursor = await self.get_own(user, cursor_id)
        rows = await self.checkup_repo.list_page(user.id, limit + 1, cursor)
        has_next = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [serialize(row) for row in rows],
            "next_cursor": rows[-1].id if has_next else None,
        }

    async def get(self, user: User, record_id: int) -> dict[str, Any]:
        """4-3."""
        return serialize(await self.get_own(user, record_id))

    async def update(self, user: User, record_id: int, data: CheckupRecordUpdateRequest) -> dict[str, Any]:
        """4-4. 보낸 필드만, 합친 값으로 규칙 검사. 지난 예측 행은 그대로.

        수정 전이나 후에 이 기록이 가장 최근 검진이면 다시 예측 (가장 최근 검진의 날짜를 예전으로 옮기면
        다른 기록이 최근이 되므로 그 기록으로 다시 판정해야 함, #103 리뷰).
        """
        record = await self.get_own(user, record_id)
        changes = data.changes()
        merged = {field: getattr(record, field) for field in ("checked_on", *CHECKUP_VALUE_FIELDS)} | changes
        check_checkup_values(merged, today_kst())
        was_latest = await self.is_latest(user, record.id)
        record = await self.checkup_repo.update(record, changes)

        if was_latest or await self.is_latest(user, record.id):
            prediction = await self.prediction_service.repredict_latest(user)
        else:
            prediction = {"predictions": [], "managed_diseases": [], "skipped_reason": None, "prediction_error": False}
        return {"checkup_record": serialize(record), **prediction}

    async def delete(self, user: User, record_id: int) -> None:
        """4-5. 지난 예측 행의 checkup_record_id는 null로 (FK SET NULL).

        지운 기록이 가장 최근 검진이었으면 다시 예측 (남은 최근 검진으로 판정, 없으면 기준표 행 없이 → 5-2에서 안 보임).
        """
        record = await self.get_own(user, record_id)
        was_latest = await self.is_latest(user, record.id)
        await self.checkup_repo.delete(record)
        if was_latest:
            await self.prediction_service.repredict_latest(user)

    async def is_latest(self, user: User, record_id: int) -> bool:
        latest = await self.checkup_repo.get_latest(user.id)
        return latest is not None and latest.id == record_id

    async def get_own(self, user: User, record_id: int) -> CheckupRecord:
        record = await self.checkup_repo.get_for_user(user.id, record_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
        return record


def today_kst() -> date:
    return datetime.now(KST).date()


def serialize(record: CheckupRecord) -> dict[str, Any]:
    body: dict[str, Any] = {"id": record.id, "checked_on": record.checked_on.isoformat()}
    for field in CHECKUP_VALUE_FIELDS:
        value = getattr(record, field)
        body[field] = float(value) if isinstance(value, Decimal) else value
    body["source"] = record.source.value
    body["created_at"] = record.created_at.astimezone(KST).isoformat()
    body["updated_at"] = record.updated_at.astimezone(KST).isoformat()
    return body
