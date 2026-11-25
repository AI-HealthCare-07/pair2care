from typing import Any

from tortoise.expressions import Q

from app.models.checkup_records import CheckupRecord


class CheckupRecordRepository:
    def __init__(self) -> None:
        self._model = CheckupRecord

    async def create(self, user_id: int, values: dict[str, Any]) -> CheckupRecord:
        return await self._model.create(user_id=user_id, **values)

    async def get_for_user(self, user_id: int, record_id: int) -> CheckupRecord | None:
        """내 기록만. 남의 id면 None → 404 (존재 여부를 숨김)."""
        return await self._model.get_or_none(id=record_id, user_id=user_id)

    async def list_page(self, user_id: int, limit: int, cursor: CheckupRecord | None) -> list[CheckupRecord]:
        """검진 날짜 최신순. 날짜가 같으면 나중에 넣은 것 먼저. cursor 행보다 뒤(오래된)부터."""
        query = self._model.filter(user_id=user_id)
        if cursor is not None:
            query = query.filter(
                Q(checked_on__lt=cursor.checked_on) | Q(checked_on=cursor.checked_on, id__lt=cursor.id)
            )
        return await query.order_by("-checked_on", "-id").limit(limit)

    async def get_latest(self, user_id: int) -> CheckupRecord | None:
        """가장 최근에 받은 검진 (예측 기준표·대사증후군이 쓰는 1건, api.md 5-1)."""
        return await self._model.filter(user_id=user_id).order_by("-checked_on", "-id").first()

    async def update(self, record: CheckupRecord, changes: dict[str, Any]) -> CheckupRecord:
        for field, value in changes.items():
            setattr(record, field, value)
        await record.save()  # updated_at은 auto_now로 갱신
        return record

    async def delete(self, record: CheckupRecord) -> None:
        # 이 기록을 참조한 risk_predictions.checkup_record_id는 FK ON DELETE SET NULL로 null (이력은 input_snapshot에 남음)
        await record.delete()
