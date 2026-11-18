import asyncio

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from ai_worker.core import config
from ai_worker.core import default_logger as logger
from ai_worker.schemas.task import GROUP_NAME, RESULT_CHANNEL, STREAM_KEY, TaskMessage, TaskType

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
                task = TaskMessage.model_validate_json(
                    fields["payload"]
                )  # FastAPI에서 XADD 할 때 {"payload": task.model_dump_json()} 형태로 넣기로 약속
                logger.info("작업 받음: %s %s", task.task_type, task.task_id)

                await handle(task)

                # xack : "처리 끝났어" 표시하여 Pending 목록에서 제거
                await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
                # publish : FastAPI가 SSE로 넘길 때 user_id, task_id, target_id를 알 수 있도록 JSON 통째로 발행
                await redis.publish(RESULT_CHANNEL, task.model_dump_json())


if __name__ == "__main__":
    asyncio.run(main())
