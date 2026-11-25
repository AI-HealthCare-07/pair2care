from datetime import datetime
from typing import Any

from tortoise import BaseDBAsyncClient

from app.models.health_logs import HealthLog, HealthLogType


class HealthLogRepository:
    def __init__(self) -> None:
        self._model = HealthLog

    async def create(self, using_db: BaseDBAsyncClient | None = None, **values: Any) -> HealthLog:
        return await self._model.create(using_db=using_db, **values)

    async def get_for_user(self, user_id: int, log_id: int) -> HealthLog | None:
        """내 기록만. 남의 id면 None → 404."""
        return await self._model.get_or_none(id=log_id, user_id=user_id)

    async def find_in_range(
        self,
        user_id: int,
        log_type: HealthLogType,
        start: datetime,
        end: datetime,
        using_db: BaseDBAsyncClient | None = None,
    ) -> HealthLog | None:
        """[start, end)에 있는 그 종류 기록 1개 (하루 1행·주 1행 덮어쓰기용)."""
        query = self._model.filter(user_id=user_id, log_type=log_type, measured_at__gte=start, measured_at__lt=end)
        if using_db is not None:
            query = query.using_db(using_db)
        return await query.order_by("-measured_at", "-id").first()

    async def list_in_range(
        self, user_id: int, log_types: list[HealthLogType], start: datetime, end: datetime, limit: int
    ) -> list[HealthLog]:
        """그래프용: measured_at 오름차순, 최대 limit개."""
        return (
            await self._model.filter(
                user_id=user_id, log_type__in=log_types, measured_at__gte=start, measured_at__lt=end
            )
            .order_by("measured_at", "id")
            .limit(limit)
        )

    async def list_at(self, user_id: int, log_types: list[HealthLogType], measured_at: datetime) -> list[HealthLog]:
        """주간 기록: 그 주 월요일 00:00에 저장된 행들."""
        return await self._model.filter(user_id=user_id, log_type__in=log_types, measured_at=measured_at)

    async def update(
        self, record: HealthLog, changes: dict[str, Any], using_db: BaseDBAsyncClient | None = None
    ) -> HealthLog:
        for field, value in changes.items():
            setattr(record, field, value)
        await record.save(using_db=using_db)  # updated_at은 auto_now
        return record

    async def delete(self, record: HealthLog, using_db: BaseDBAsyncClient | None = None) -> None:
        await record.delete(using_db=using_db)
