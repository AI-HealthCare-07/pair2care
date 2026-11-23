import asyncio
import json
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from tortoise.contrib.test import TruncationTestCase

from ai_worker.core import config
from ai_worker.main import ensure_group, process_message
from ai_worker.schemas.task import GROUP_NAME, RESULT_CHANNEL, STREAM_KEY, TaskMessage
from ai_worker.tasks.llm_recommendation import NO_EVIDENCE, ClaudeCallError
from ai_worker.tasks.recommendation_runner import run_recommendation
from app.main import app
from app.models.llm_usage_logs import LlmUsageLog
from app.models.recommendations import Recommendation
from app.models.users import User
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data

DAILY = "/api/v1/recommendations/daily"
EMAIL = "recommendation@example.com"


async def read_task(redis: Redis) -> tuple[str, dict[str, str]]:
    streams = await redis.xreadgroup(GROUP_NAME, "recommendation-test", {STREAM_KEY: ">"}, count=1, block=2000)
    assert streams
    return streams[0][1][0]


class TestRecommendations(TruncationTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.client = await self.enterAsyncContext(
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        )
        signup = await self.client.post("/api/v1/auth/signup", json=make_signup_data(EMAIL))
        assert signup.status_code == 201
        login = await self.client.post("/api/v1/auth/login", json={"email": EMAIL, "password": DEFAULT_PASSWORD})
        self.client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        self.redis = await self.enterAsyncContext(
            Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
        )
        await ensure_group(self.redis)

    async def test_daily_deduplicates_and_completes_through_redis(self) -> None:
        client = self.client
        redis = self.redis
        assert (await client.get(DAILY)).status_code == 404
        assert (await client.get(DAILY, params={"target_on": "invalid"})).status_code == 422
        responses = await asyncio.gather(client.post(DAILY), client.post(DAILY))
        created, existing = sorted(responses, key=lambda response: -response.status_code)
        assert (created.status_code, existing.status_code) == (202, 200)
        assert existing.json()["id"] == created.json()["recommendation_id"]
        message_id, fields = await read_task(redis)
        task = TaskMessage.model_validate_json(fields["payload"])
        assert task.task_id == created.json()["task_id"]
        async with redis.pubsub() as results:
            await results.subscribe(RESULT_CHANNEL)
            await process_message(redis, message_id, fields)
            async with asyncio.timeout(2):
                async for event in results.listen():
                    if event["type"] == "message":
                        assert json.loads(event["data"])["status"] == "COMPLETED"
                        break
        saved = (await client.get(DAILY)).json()
        assert saved["status"] == "COMPLETED"
        assert saved["content"] == NO_EVIDENCE
        assert saved["sources"] == []
        assert not await LlmUsageLog.filter(recommendation_id=task.target_id).exists()

    async def test_queue_error_does_not_count_as_model_failure(self) -> None:
        client = self.client
        self.enterContext(patch.object(Redis, "xadd", AsyncMock(side_effect=RedisConnectionError())))
        assert (await client.post(DAILY)).status_code == 503
        saved = (await client.get(DAILY)).json()
        assert saved["status"] == "FAILED"
        assert saved["retry_count"] == 0

    async def test_worker_retry_limit_and_stale_task(self) -> None:
        client = self.client
        redis = self.redis
        failing_model = AsyncMock(side_effect=ClaudeCallError("mock"))
        self.enterContext(patch("ai_worker.tasks.recommendation_runner.generate_recommendation", failing_model))
        self.enterContext(patch("ai_worker.main.MAX_ATTEMPTS", 1))
        previous = None
        for attempt in range(1, 4):
            response = await client.post(DAILY)
            assert response.status_code == 202
            message_id, fields = await read_task(redis)
            if previous is not None:
                await process_message(redis, *previous)
                assert (await client.get(DAILY)).json()["status"] == "PENDING"
                assert failing_model.await_count == attempt - 1
            await process_message(redis, message_id, fields)
            saved = (await client.get(DAILY)).json()
            assert saved["status"] == "FAILED"
            assert saved["retry_count"] == attempt
            assert saved["id"] == response.json()["recommendation_id"]
            previous = message_id, fields
        assert (await client.post(DAILY)).status_code == 429
        assert await LlmUsageLog.filter(recommendation_id=saved["id"], is_success=False).count() == 3

    async def test_meal_ownership_selection_and_usage(self) -> None:
        client = self.client
        redis = self.redis
        db = Recommendation._meta.db
        user = await User.get(email=EMAIL)
        await db.execute_script(
            """
            CREATE TABLE foods (id BIGINT PRIMARY KEY, name VARCHAR(150) NOT NULL);
            CREATE TABLE meals (
                id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL, food_id BIGINT,
                eaten_at DATETIME NOT NULL, category VARCHAR(10), portion DECIMAL(2,1), nutrients JSON
            );
            INSERT INTO foods VALUES (1, '국밥');
            """
        )
        try:
            await db.execute_query(
                """INSERT INTO meals VALUES
                    (1, %s, NULL, '2026-11-20 09:00:00', 'MEAL', 1.5, '{"sodium_mg": 900}'),
                    (2, 0, 1, '2026-11-20 09:00:00', 'MEAL', 1.5, NULL)""",
                [user.id],
            )
            assert (await client.get("/api/v1/meals/2/recommendation")).status_code == 404
            assert (await client.post("/api/v1/meals/1/recommendation")).status_code == 409
            await db.execute_query("UPDATE meals SET food_id=1 WHERE id=1")
            assert (await client.post("/api/v1/meals/2/recommendation")).status_code == 404

            selector = AsyncMock(return_value=("htn_less_salt", {"input_tokens": 7, "output_tokens": 2}))
            self.enterContext(patch("ai_worker.tasks.llm_recommendation.AnthropicSelector.choose", selector))
            response = await client.post("/api/v1/meals/1/recommendation")
            assert response.status_code == 202
            message_id, fields = await read_task(redis)
            task = TaskMessage.model_validate_json(fields["payload"])
            await asyncio.gather(run_recommendation(task), run_recommendation(task))
            await process_message(redis, message_id, fields)
            selector.assert_awaited_once()
            prompt, _ = selector.await_args.args
            assert json.loads(prompt)["meal_facts"] == {"sodium_mg": 900, "portion": 1.5}
            assert "국밥" not in prompt
            result = (await client.get("/api/v1/meals/1/recommendation")).json()
            assert result["status"] == "COMPLETED"
            assert result["target_on"] == "2026-11-20"
            assert result["sources"][0]["number"] == 1
            usage = await LlmUsageLog.get(recommendation_id=result["id"])
            assert (usage.meal_id, usage.input_tokens, usage.output_tokens, usage.is_success) == (1, 7, 2, True)
        finally:
            await db.execute_script("DROP TABLE meals; DROP TABLE foods;")
