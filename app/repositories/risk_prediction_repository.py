from typing import Any

from tortoise import BaseDBAsyncClient

from app.models.checkup_records import CheckupRecord
from app.models.risk_predictions import PredictionMethod, RiskPrediction


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

    async def list_for_profile(self, health_profile_id: int) -> list[RiskPrediction]:
        return await self._model.filter(health_profile_id=health_profile_id).all()

    async def get_for_user(self, user_id: int, prediction_id: int) -> RiskPrediction | None:
        """내 예측만. 남의 id면 None → 404 (존재 여부를 숨김)."""
        return await self._model.get_or_none(id=prediction_id, user_id=user_id)

    async def get_previous_model_row(self, row: RiskPrediction) -> RiskPrediction | None:
        """같은 질환, 이전 설문의 가장 최근 MODEL 행 (changed_inputs·previous 비교 대상).

        검진 저장(4-1·4-4)으로 같은 설문에 MODEL 행이 다시 생겨도, 비교는 지난 설문과 함 (같은 설문끼리면 변화가 없어 보임).
        """
        return (
            await self._model.filter(
                user_id=row.user_id,
                disease=row.disease,
                method=PredictionMethod.MODEL,
                id__lt=row.id,
            )
            .exclude(health_profile_id=row.health_profile_id)
            .order_by("-created_at", "-id")
            .first()
        )
