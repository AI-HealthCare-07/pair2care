"""Redis 추천 작업의 입력 조회, 상태 전환 및 사용량 기록."""

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from tortoise import Tortoise
from tortoise.exceptions import OperationalError
from tortoise.transactions import in_transaction

from ai_worker.schemas.task import KST, TaskMessage
from ai_worker.tasks.llm_recommendation import MODEL, ClaudeCallError, RecommendationResult, generate_recommendation
from app.core.db.databases import TORTOISE_ORM
from app.models.llm_usage_logs import LlmUsageLog
from app.models.recommendations import GenerationStatus, Recommendation, RecommendationType


async def _init_db() -> None:
    # Worker의 소비 루프는 작업을 순차적으로 실행한다.
    if Recommendation._meta.default_connection is None:
        await Tortoise.init(config=TORTOISE_ORM)


def _estimated_cost(result: RecommendationResult) -> Decimal | None:
    # 캐시 토큰은 별도 단가가 필요하다.
    if result.cache_creation_tokens or result.cache_read_tokens:
        return None
    try:
        input_rate = Decimal(os.environ["CLAUDE_INPUT_USD_PER_MILLION"])
        output_rate = Decimal(os.environ["CLAUDE_OUTPUT_USD_PER_MILLION"])
        amount = (result.input_tokens * input_rate + result.output_tokens * output_rate) / 1_000_000
        if amount.is_finite() and 0 <= amount < 10_000:
            return amount.quantize(Decimal("0.000001"))
    except (KeyError, ArithmeticError):
        pass
    return None


async def _gather_facts(rec: Recommendation) -> dict[str, Any]:
    db = Recommendation._meta.db
    try:
        if rec.rec_type == RecommendationType.DAILY_ACTION:
            rows = await db.execute_query_dict(
                """SELECT is_hypertension_diagnosed, is_diabetes_diagnosed
                   FROM health_profiles WHERE user_id=%s ORDER BY created_at DESC, id DESC LIMIT 1""",
                [rec.user_id],
            )
            return rows[0] if rows else {}

        rows = await db.execute_query_dict(
            """SELECT f.name, m.category, m.portion, m.nutrients
               FROM meals m JOIN foods f ON f.id=m.food_id
               WHERE m.id=%s AND m.user_id=%s LIMIT 1""",
            [rec.meal_id, rec.user_id],
        )
    except OperationalError as exc:
        # develop에 팀의 테이블이 들어오기 전까지는 근거 부족으로 처리한다.
        if exc.args and getattr(exc.args[0], "args", ())[:1] == (1146,):
            return {}
        raise

    if not rows:
        return {}
    row = rows[0]
    nutrients = row["nutrients"]
    if isinstance(nutrients, str):
        nutrients = json.loads(nutrients)
    facts = (
        {key: nutrients.get(key) for key in ("sodium_mg", "sugar_g", "carbs_g")} if isinstance(nutrients, dict) else {}
    )
    facts["is_drink"] = row["category"] == "DRINK"
    facts["is_broth_dish"] = any(word in row["name"] for word in ("국물", "국밥", "찌개", "탕", "라면"))
    facts["portion"] = row["portion"]
    return facts


async def run_recommendation(task: TaskMessage) -> None:
    await _init_db()
    try:
        task_id = UUID(task.task_id)
    except ValueError:
        return
    query = Recommendation.filter(id=task.target_id, user_id=task.user_id, task_id=task_id)
    await query.filter(status=GenerationStatus.PENDING).update(
        status=GenerationStatus.PROCESSING, updated_at=datetime.now(KST)
    )
    try:
        async with in_transaction(Recommendation._meta.default_connection) as conn:
            rec = await query.using_db(conn).select_for_update().first()
            if rec is None or rec.status != GenerationStatus.PROCESSING:
                return

            # 행 잠금은 중복 호출을 막고, 워커가 종료되면 다른 소비자가 이어서 처리한다.
            result = await generate_recommendation(rec.rec_type.value, await _gather_facts(rec))
            rec.content = result.content
            rec.sources = result.sources
            rec.model = result.model
            rec.prompt_version = result.prompt_version
            rec.status = GenerationStatus.COMPLETED
            await rec.save(using_db=conn)
            if result.called_model:
                await LlmUsageLog.create(
                    using_db=conn,
                    user_id=rec.user_id,
                    recommendation_id=rec.id,
                    meal_id=rec.meal_id,
                    feature=rec.rec_type.value,
                    model=MODEL,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cache_creation_tokens=result.cache_creation_tokens,
                    cache_read_tokens=result.cache_read_tokens,
                    estimated_cost_usd=_estimated_cost(result),
                    is_success=True,
                )
    except ClaudeCallError:
        await LlmUsageLog.create(
            user_id=rec.user_id,
            recommendation_id=rec.id,
            meal_id=rec.meal_id,
            feature=rec.rec_type.value,
            model=MODEL,
            is_success=False,
        )
        raise


async def recommendation_status(task: TaskMessage, *, mark_failed: bool = False) -> GenerationStatus | None:
    """현재 작업의 결과만 반환한다. 이전 세대 메시지의 알림은 생략한다."""
    await _init_db()
    async with in_transaction(Recommendation._meta.default_connection) as conn:
        rec = (
            await Recommendation.filter(id=task.target_id, user_id=task.user_id)
            .using_db(conn)
            .select_for_update()
            .first()
        )
        if rec is None or str(rec.task_id) != task.task_id:
            return None
        if mark_failed and rec.status in (GenerationStatus.PENDING, GenerationStatus.PROCESSING):
            rec.status = GenerationStatus.FAILED
            rec.retry_count += 1
            await rec.save(using_db=conn, update_fields=["status", "retry_count", "updated_at"])
        return rec.status
