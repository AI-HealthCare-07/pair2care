"""공통 SSE (api.md 12-6): 티켓 발급 + 이벤트 스트림.

흐름
1. 로그인한 화면이 POST /events/ticket → 1회용 티켓(30초)을 Redis에 저장하고 돌려줌
2. 브라우저 EventSource가 GET /events?ticket=... 로 연결 → 티켓을 꺼내면서 지움(GETDEL, 1회용)
3. 연결이 열려 있는 동안 Redis Pub/Sub `ai:results`(AI 워커가 작업 끝나면 발행)를 구독하고,
   이 사람(user_id) 것만 골라 `event: task`로 내려줌. 30초 동안 보낼 게 없으면 `: ping`으로 연결 유지

왜 티켓인가: EventSource는 Authorization 헤더를 못 붙임. access 토큰을 URL에 넣으면 nginx·서버 로그에 남아서,
30초짜리 1회용 티켓을 따로 둠 (정할 것 20번).
"""

import json
import secrets
import time
from collections.abc import AsyncGenerator
from typing import Any, Final

from pydantic import ValidationError
from redis.asyncio import Redis

from app.core import config
from app.core import default_logger as logger
from shared.tasks import RESULT_CHANNEL, TaskResult

TICKET_KEY_PREFIX: Final = "sse:ticket:"  # Redis 키: sse:ticket:<티켓> → user_id
TICKET_TTL_SECONDS: Final = 30  # 티켓 유효 시간 (api.md 12-6)
PING_SECONDS: Final = 30  # 이 시간 동안 보낸 게 없으면 ping (nginx proxy_read_timeout 60초보다 짧게)
TASK_EVENT_FIELDS: Final = (
    "task_id",
    "task_type",
    "target_id",
    "status",
)  # task 이벤트에 내려주는 4개 (user_id는 안 넣음)


def redis_client() -> Redis:
    # decode_responses=True: GETDEL·Pub/Sub 값을 bytes가 아니라 str로 받음
    return Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)


async def issue_ticket(user_id: int) -> dict[str, Any]:
    """1회용 SSE 티켓 발급. 추측할 수 없게 secrets로 만들고, 30초 뒤 Redis가 알아서 지움."""
    ticket = secrets.token_urlsafe(32)
    async with redis_client() as redis:
        await redis.set(f"{TICKET_KEY_PREFIX}{ticket}", user_id, ex=TICKET_TTL_SECONDS)
    return {"ticket": ticket, "expires_in": TICKET_TTL_SECONDS}


async def use_ticket(ticket: str) -> int | None:
    """티켓을 꺼내면서 지움 → 같은 티켓으로 두 번 연결 못 함. 없거나 만료면 None (라우터가 401)."""
    async with redis_client() as redis:
        user_id = await redis.getdel(f"{TICKET_KEY_PREFIX}{ticket}")
    return int(user_id) if user_id is not None else None


def format_event(event: str, data: dict[str, Any]) -> str:
    """SSE 한 덩어리: `event: 이름` + `data: JSON` + 빈 줄. 한글이 그대로 보이게 ensure_ascii=False."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def task_event_for(user_id: int, raw: str) -> str | None:
    """ai:results 메시지 하나 → 이 사람 것이면 task 이벤트 문자열, 아니면 None.

    모양이 깨진 메시지는 로그만 남기고 버림 (한 메시지 때문에 연결이 끊기지 않게).
    """
    try:
        result = TaskResult.model_validate_json(raw)
    except ValidationError:
        logger.warning("SSE: ai:results 메시지 형식이 맞지 않아 건너뜀")
        return None
    if result.user_id != user_id:
        return None
    payload = result.model_dump(mode="json", include=set(TASK_EVENT_FIELDS))
    return format_event("task", payload)


async def event_stream(user_id: int, ping_seconds: float = PING_SECONDS) -> AsyncGenerator[str]:
    """한 연결 동안 도는 제너레이터. 브라우저가 끊으면 Starlette가 이 제너레이터를 닫아서 구독도 같이 정리됨.

    shortcut: 연결마다 Redis 구독을 하나씩 엶 (사용자 수가 적은 데모 규모 기준).
    동시 접속이 수백 명이 되면 프로세스당 구독 1개 + 메모리에서 나눠 주는 방식으로 바꿀 것.
    """
    async with redis_client() as redis, redis.pubsub() as pubsub:
        await pubsub.subscribe(RESULT_CHANNEL)
        # 연결 직후 한 번 보냄: 프록시가 응답 헤더를 바로 넘기게 하고, 끊겼을 때 다시 연결까지 3초 기다리라고 알려 줌
        yield "retry: 3000\n: connected\n\n"
        last_sent = time.monotonic()
        while True:
            # 다음 ping까지 남은 시간만큼만 기다림 → 다른 사람 메시지만 계속 와도 ping은 제때 나감
            wait = max(0.0, ping_seconds - (time.monotonic() - last_sent))
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=wait)
            if message is not None and message["type"] == "message":
                event = task_event_for(user_id, message["data"])
                if event is not None:
                    yield event
                    last_sent = time.monotonic()
                    continue
            if time.monotonic() - last_sent >= ping_seconds:
                yield ": ping\n\n"  # 콜론으로 시작하는 줄은 주석 → 브라우저는 무시하고 연결만 유지됨
                last_sent = time.monotonic()
