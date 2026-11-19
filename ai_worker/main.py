import asyncio
import json

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from ai_worker.core import config
from ai_worker.core import default_logger as logger
from ai_worker.schemas.task import DEAD_LETTER_KEY, GROUP_NAME, RESULT_CHANNEL, STREAM_KEY, TaskMessage, TaskType

CONSUMER_NAME = "worker-1"  # 워커가 여러 대면 이름을 다르게


async def ensure_group(redis: Redis) -> None:
    """Consumer Group이 없으면 만든다. 이미 있으면 그냥 넘어감."""
    try:
        await redis.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
        # id="0" : 워커가 꺼져 있던 동안 쌓인 메시지도 모두 읽어옴
        # mkstream=True : FastAPI보다 워커가 먼저 실행되어도 스트림을 자동 생성
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):  # 그룹이 이미 있을 때 Redis가 주는 에러 이름
            raise


async def handle(task: TaskMessage) -> None:
    """작업 종류별로 처리. 지금은 가짜(mock)로 잠깐 기다리기만 함."""
    if task.task_type == TaskType.MEAL_CLASSIFY:
        await asyncio.sleep(1)  # TODO: 현지님 분류 함수로 교체
    elif task.task_type == TaskType.RECOMMEND_LLM:
        await asyncio.sleep(1)  # TODO: 민준님 LLM 함수로 교체
    else:
        logger.warning("처리 함수가 없는 작업 종류: %s (task_id=%s)", task.task_type, task.task_id)


MAX_ATTEMPTS = 3


async def run_with_retry(task: TaskMessage) -> bool:
    """성공하면 True, 3번 다 실패하면 False"""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await handle(task)
            return True
        except Exception:
            logger.exception("작업 실패 (%s/%s): %s", attempt, MAX_ATTEMPTS, task.task_id)
            if attempt < MAX_ATTEMPTS:
                # attempt=1 -> 2**0 = 1초 대기, attempt=2 -> 2**1 = 2초 대기
                await asyncio.sleep(2 ** (attempt - 1))
    return False


async def process_message(redis: Redis, message_id: str, fields: dict[str, str]) -> None:
    # A. 깨진 메시지 → 재시도 없이 dead-letter
    try:
        task = TaskMessage.model_validate_json(fields["payload"])
    except (KeyError, ValidationError):  # 💡 fields에 "payload"가 아예 없을 때 나는 에러 이름은?
        logger.error("깨진 메시지: %s", message_id)  # 💡 왜 payload 내용은 로그에 안 찍을까?
        await redis.xadd(DEAD_LETTER_KEY, {"message_id": message_id, "reason": "INVALID_MESSAGE"})
        await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
        return

    logger.info("작업 받음: %s %s", task.task_type, task.task_id)

    # B. 처리 (최대 3번)
    is_success = await run_with_retry(task)
    if not is_success:
        await redis.xadd(
            DEAD_LETTER_KEY, {"message_id": message_id, "reason": "MAX_RETRY_EXCEEDED", "payload": fields["payload"]}
        )
        # TODO 5단계: DB status = FAILED

    await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
    status = "COMPLETED" if is_success else "FAILED"
    await redis.publish(RESULT_CHANNEL, json.dumps({**task.model_dump(mode="json"), "status": status}))


async def main() -> None:
    redis = Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
    await ensure_group(redis)
    logger.info("워커 시작: %s", CONSUMER_NAME)

    while True:
        # ">"  : "아직 아무도 안 가져간 새 메시지만" 이라는 뜻
        streams = await redis.xreadgroup(
            GROUP_NAME,
            CONSUMER_NAME,
            {STREAM_KEY: ">"},
            count=1,
            block=5000,  # 메시지가 없으면 5초 기다림
        )
        if not streams:
            continue

        for _stream, messages in streams:
            for message_id, fields in messages:
                await process_message(redis, message_id, fields)


if __name__ == "__main__":
    asyncio.run(main())
