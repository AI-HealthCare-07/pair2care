from datetime import date
from uuid import UUID

from tortoise import BaseDBAsyncClient

from app.models.recommendations import GenerationStatus, Recommendation, RecommendationType
from app.models.users import User


class RecommendationRepository:
    @staticmethod
    async def daily(user_id: int, target_on: date) -> Recommendation | None:
        return await Recommendation.filter(
            user_id=user_id, rec_type=RecommendationType.DAILY_ACTION, target_on=target_on
        ).first()

    @staticmethod
    async def meal(user_id: int, meal_id: int) -> Recommendation | None:
        return await Recommendation.filter(
            user_id=user_id, rec_type=RecommendationType.MEAL_ALTERNATIVE, meal_id=meal_id
        ).first()

    @staticmethod
    async def prepare(
        conn: BaseDBAsyncClient,
        user_id: int,
        kind: RecommendationType,
        target_on: date,
        meal_id: int | None,
        task_id: UUID,
    ) -> tuple[Recommendation | None, bool, str]:
        """사용자 행을 잠그고 큐 등록이 끝날 때까지 중복 요청을 직렬화한다."""
        user = await User.filter(id=user_id).using_db(conn).select_for_update().first()
        if not user or not user.is_active:
            return None, False, "NOT_FOUND"
        filters = {"user_id": user_id, "rec_type": kind}
        if kind == RecommendationType.DAILY_ACTION:
            filters["target_on"] = target_on
        else:
            filters["meal_id"] = meal_id
        rec = await Recommendation.filter(**filters).using_db(conn).first()
        if rec is None:
            rec = await Recommendation.create(
                using_db=conn,
                user_id=user_id,
                rec_type=kind,
                target_on=target_on,
                meal_id=meal_id,
                task_id=task_id,
            )
            return rec, True, "NEW"
        if rec.status != GenerationStatus.FAILED:
            return rec, False, "EXISTS"
        if rec.retry_count >= 3:
            return rec, False, "LIMIT"
        rec.status = GenerationStatus.PENDING
        rec.task_id = task_id
        rec.content = None
        rec.sources = None
        rec.model = None
        rec.prompt_version = None
        await rec.save(using_db=conn)
        return rec, True, "RETRY"
