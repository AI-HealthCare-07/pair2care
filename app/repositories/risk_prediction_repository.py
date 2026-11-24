from typing import Any

from tortoise import BaseDBAsyncClient

from app.models.checkup_records import CheckupRecord
from app.models.risk_predictions import RiskPrediction


class RiskPredictionRepository:
    def __init__(self) -> None:
        self._model = RiskPrediction

    async def create(self, using_db: BaseDBAsyncClient | None = None, **values: Any) -> RiskPrediction:
        return await self._model.create(using_db=using_db, **values)

    async def get_latest_checkup(self, user_id: int, using_db: BaseDBAsyncClient | None = None) -> CheckupRecord | None:
        """가장 최근에 받은 검진 1건 (api.md 5-1: 최근 1건만 씀, 유효기간은 서비스에서 봄)."""
        query = CheckupRecord.filter(user_id=user_id).order_by("-checked_on", "-id")
        if using_db is not None:
            query = query.using_db(using_db)
        return await query.first()
