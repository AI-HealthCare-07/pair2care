"""12-6 공통 SSE: 티켓(30초·1회용)과 task 이벤트 거르기 (진짜 Redis 사용)."""

import asyncio
import json

from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from starlette import status
from tortoise.contrib.test import TestCase

from app.apis.v1.event_routers import stream_events
from app.core import config
from app.main import app
from app.services.events import TICKET_KEY_PREFIX, TICKET_TTL_SECONDS, event_stream, task_event_for
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from shared.tasks import RESULT_CHANNEL, TaskMessage, TaskResult, TaskType

EMAIL = "events@example.com"


def result_json(user_id: int, target_id: int = 101) -> str:
    task = TaskMessage(task_type=TaskType.MEAL_CLASSIFY, user_id=user_id, target_id=target_id)
    return TaskResult.model_validate({**task.model_dump(), "status": "COMPLETED"}).model_dump_json()


class TestEventTicket(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.client = await self.enterAsyncContext(
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        )
        await self.client.post("/api/v1/auth/signup", json=make_signup_data(EMAIL))
        login = await self.client.post("/api/v1/auth/login", json={"email": EMAIL, "password": DEFAULT_PASSWORD})
        self.auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
        self.redis = await self.enterAsyncContext(
            Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
        )

    async def test_ticket_needs_login(self) -> None:
        response = await self.client.post("/api/v1/events/ticket")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_ticket_is_saved_for_30_seconds(self) -> None:
        response = await self.client.post("/api/v1/events/ticket", headers=self.auth)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["expires_in"] == TICKET_TTL_SECONDS
        key = f"{TICKET_KEY_PREFIX}{body['ticket']}"
        assert 0 < await self.redis.ttl(key) <= TICKET_TTL_SECONDS

    async def test_missing_or_unknown_ticket_is_401(self) -> None:
        assert (await self.client.get("/api/v1/events")).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        response = await self.client.get("/api/v1/events", params={"ticket": "nope"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_ticket_is_one_time(self) -> None:
        # httpx ASGITransport는 응답 본문을 끝까지 모아서 돌려주는데 SSE는 안 끝남
        # → 라우터 함수를 직접 불러 응답 모양만 보고, 스트림은 열지 않고 닫음
        ticket = (await self.client.post("/api/v1/events/ticket", headers=self.auth)).json()["ticket"]
        response = await stream_events(ticket)
        assert response.media_type == "text/event-stream"
        assert response.headers["x-accel-buffering"] == "no"
        await response.body_iterator.aclose()  # type: ignore[attr-defined]
        assert await self.redis.exists(f"{TICKET_KEY_PREFIX}{ticket}") == 0  # 쓰자마자 지워짐
        second = await self.client.get("/api/v1/events", params={"ticket": ticket})
        assert second.status_code == status.HTTP_401_UNAUTHORIZED


class TestTaskEvent(TestCase):
    def test_only_my_result_with_four_fields(self) -> None:
        assert task_event_for(7, result_json(user_id=8)) is None
        event = task_event_for(7, result_json(user_id=7))
        assert event is not None
        name, data = event.strip().split("\n")
        assert name == "event: task"
        payload = json.loads(data.removeprefix("data: "))
        assert set(payload) == {"task_id", "task_type", "target_id", "status"}  # user_id는 응답에 안 넣음
        assert payload["task_type"] == "MEAL_CLASSIFY"

    def test_broken_message_is_skipped(self) -> None:
        assert task_event_for(7, "not json") is None

    async def test_stream_sends_my_task_and_ping(self) -> None:
        stream = event_stream(user_id=7, ping_seconds=0.5)
        try:
            assert (await anext(stream)).startswith("retry: 3000")  # 연결 직후 (이때 구독은 이미 끝남)
            async with Redis(host=config.REDIS_HOST, port=config.REDIS_PORT) as redis:
                await redis.publish(RESULT_CHANNEL, result_json(user_id=8))  # 남의 것 → 안 옴
                await redis.publish(RESULT_CHANNEL, result_json(user_id=7, target_id=555))
            mine = await asyncio.wait_for(anext(stream), timeout=2)
            assert mine.startswith("event: task") and '"target_id": 555' in mine
            assert await asyncio.wait_for(anext(stream), timeout=2) == ": ping\n\n"
        finally:
            await stream.aclose()
