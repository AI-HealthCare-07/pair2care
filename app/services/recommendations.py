"""추천 생성/조회 서비스. LLM 요청 자체는 AI Worker에서 실행한다."""

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from tortoise.exceptions import OperationalError
from tortoise.transactions import in_transaction

from app.core import config
from app.dtos.recommendations import RecommendationQueued, RecommendationRead
from app.models.recommendations import GenerationStatus, Recommendation, RecommendationType
from app.repositories.recommendation_repository import RecommendationRepository
from shared.tasks import STREAM_KEY, TaskMessage, TaskType

KST = ZoneInfo("Asia/Seoul")
QUEUE_ERROR = "작업을 시작하지 못했어요. 잠시 후 다시 시도해 주세요."


class RecommendationService:
    def __init__(self) -> None:
        self.repo = RecommendationRepository()

    @staticmethod
    def to_read(rec: Recommendation) -> dict:
        return RecommendationRead.model_validate(rec).model_dump(mode="json")

    async def get_daily(self, user_id: int, target_on: date | None = None) -> dict:
        row = await self.repo.daily(user_id, target_on or datetime.now(KST).date())
        if row is None:
            raise HTTPException(404, "저장된 오늘의 추천이 없어요.")
        return self.to_read(row)

    async def get_meal(self, user_id: int, meal_id: int) -> dict:
        await self._meal_for_user(user_id, meal_id)
        row = await self.repo.meal(user_id, meal_id)
        if row is None:
            raise HTTPException(404, "저장된 식단 추천이 없어요.")
        return self.to_read(row)

    @staticmethod
    async def _meal_for_user(user_id: int, meal_id: int) -> dict:
        """다른 사용자 식단은 404. 식단 테이블이 아직 없다면 503으로 구분한다."""
        try:
            rows = await Recommendation._meta.db.execute_query_dict(
                "SELECT id, food_id, eaten_at FROM meals WHERE id=%s AND user_id=%s LIMIT 1", [meal_id, user_id]
            )
        except OperationalError as exc:
            # TODO: 여현지 담당 식단 모델·테이블 병합 후 ORM Repository로 교체
            raise HTTPException(503, "식단 기능을 준비 중이에요.") from exc
        if not rows:
            raise HTTPException(404, "식단 기록을 찾을 수 없어요.")
        return rows[0]

    async def post_daily(self, user_id: int) -> tuple[int, dict]:
        return await self._prepare(user_id, RecommendationType.DAILY_ACTION, datetime.now(KST).date())

    async def post_meal(self, user_id: int, meal_id: int) -> tuple[int, dict]:
        meal = await self._meal_for_user(user_id, meal_id)
        if meal["food_id"] is None:
            raise HTTPException(409, "음식을 골라 저장한 뒤 추천을 받아 주세요.")
        eaten = meal["eaten_at"]
        if eaten.tzinfo is None:
            # DB TIMESTAMP은 팀 설정에서 Asia/Seoul로 읽는다.
            eaten = eaten.replace(tzinfo=KST)
        return await self._prepare(user_id, RecommendationType.MEAL_ALTERNATIVE, eaten.astimezone(KST).date(), meal_id)

    async def _prepare(
        self, user_id: int, kind: RecommendationType, target_on: date, meal_id: int | None = None
    ) -> tuple[int, dict]:
        task_id = uuid4()
        queue_error = None
        async with in_transaction(Recommendation._meta.default_connection) as conn:
            row, should_queue, reason = await self.repo.prepare(conn, user_id, kind, target_on, meal_id, task_id)
            if row is None:
                raise HTTPException(404, "사용자를 찾을 수 없어요.")
            if reason == "LIMIT":
                raise HTTPException(429, "추천을 다시 요청할 수 있는 횟수를 모두 사용했어요.")
            if not should_queue:
                return 200, self.to_read(row)
            task = TaskMessage(
                task_id=str(task_id), task_type=TaskType.RECOMMEND_LLM, user_id=user_id, target_id=row.id
            )
            try:
                async with Redis(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry=Retry(NoBackoff(), 0),
                ) as redis:
                    await redis.xadd(STREAM_KEY, {"payload": task.model_dump_json()})
            except RedisError as exc:
                queue_error = exc
                row.status = GenerationStatus.FAILED
                row.task_id = None
                await row.save(using_db=conn, update_fields=["status", "task_id", "updated_at"])
        if queue_error is not None:
            raise HTTPException(503, QUEUE_ERROR) from queue_error
        return 202, RecommendationQueued(recommendation_id=row.id, task_id=str(task_id)).model_dump(mode="json")
