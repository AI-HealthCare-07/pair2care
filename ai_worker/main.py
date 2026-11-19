import asyncio
import json
import socket

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from ai_worker.core import config
from ai_worker.core import default_logger as logger
from ai_worker.schemas.task import DEAD_LETTER_KEY, GROUP_NAME, RESULT_CHANNEL, STREAM_KEY, TaskMessage, TaskType

CONSUMER_NAME = config.WORKER_NAME or socket.gethostname()
# ↑ Consumer 이름이 워커마다 달라야 "내 Pending"이 안 섞임 (같은 이름이면 두 워커가 서로의 메시지를 재처리)
#   Docker는 컨테이너를 새로 만들면 호스트명이 바뀜 → 옛 이름의 Pending은 claim_stuck이 5분 뒤 가져감
DEAD_LETTER_MAXLEN = 1000  # dead-letter가 끝없이 쌓이지 않게 대략 최근 1000건만 남김

# ── 4단계: 워커가 처리 도중 죽었을 때 남은 메시지 되살리기 ──
# 처리 중 워커가 꺼지면 XACK을 못 한 메시지가 Pending 목록(PEL)에 계속 남음.
# ">"로 읽으면 "아무도 안 가져간 새 메시지"만 오기 때문에 그 메시지는 다시 안 옴 → 아래 두 가지로 되살림
#   A. 시작할 때 내 Pending 다시 처리 (recover_own_pending)
#   B. 다른 워커가 죽어서 오래 멈춘 메시지를 뺏어 와 처리 (claim_stuck, XAUTOCLAIM)
CLAIM_IDLE_MS = 300_000  # 5분 넘게 ACK 안 된 메시지만 뺏어 옴 (밀리초)
# ↑ 정상 처리 중인 메시지를 뺏으면 같은 작업을 두 워커가 동시에 하게 됨
#   한 작업 최대 시간(처리 3번 + 재시도 대기 1초·2초, LLM은 수십 초 걸릴 수 있음)보다 넉넉해야 함
CLAIM_EVERY_SEC = 30  # 30초마다 한 번씩 멈춘 메시지 확인
MAX_DELIVERIES = 3  # 3번보다 많이 배달됐으면 독이 든 메시지(받을 때마다 워커를 죽이는 메시지)로 봄
# ↑ run_with_retry의 3번과는 다른 숫자: 이건 "워커가 죽어서 다시 배달된 횟수"


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
        # TODO 6단계: LLM 호출엔 타임아웃(예: 60초) 필수 — CLAIM_IDLE_MS(5분)는 "작업 하나가 5분 안에 끝남"이 전제
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
    except (KeyError, ValidationError):  # KeyError: fields에 "payload"가 아예 없을 때
        # payload 내용은 로그에 안 찍음: 건강 정보가 들어갈 수 있어서 (REQ-NFR-006)
        logger.error("깨진 메시지: %s", message_id)
        await redis.xadd(
            DEAD_LETTER_KEY,
            {"message_id": message_id, "reason": "INVALID_MESSAGE"},
            maxlen=DEAD_LETTER_MAXLEN,
            approximate=True,
        )
        await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
        return

    logger.info("작업 받음: %s %s", task.task_type, task.task_id)

    # B. 처리 (최대 3번)
    is_success = await run_with_retry(task)
    if not is_success:
        await redis.xadd(
            DEAD_LETTER_KEY,
            {"message_id": message_id, "reason": "MAX_RETRY_EXCEEDED", "payload": fields["payload"]},
            maxlen=DEAD_LETTER_MAXLEN,
            approximate=True,
        )
        # TODO 5단계: DB status = FAILED

    await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
    status = "COMPLETED" if is_success else "FAILED"
    await redis.publish(RESULT_CHANNEL, json.dumps({**task.model_dump(mode="json"), "status": status}))


async def handle_claimed(redis: Redis, message_id: str, fields: dict[str, str]) -> None:
    """다시 가져온 메시지: 너무 많이 배달됐으면 dead-letter, 아니면 평소처럼 처리."""
    # 스트림에서 지워지거나 잘린(MAXLEN) 메시지는 Pending에 id만 남아 fields가 None·{}로 옴
    # → 처리할 내용이 없으니 ACK만 하고 끝냄 (None이면 fields["payload"]가 TypeError라 워커가 죽음)
    if not fields:
        logger.warning("내용이 사라진 메시지, ACK만 함: %s", message_id)
        await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
        return

    # XPENDING으로 이 메시지가 지금까지 몇 번 배달됐는지 확인
    # (">"·"0"으로 읽거나 XAUTOCLAIM으로 가져올 때마다 Redis가 1씩 올림 → 지금 배달도 포함된 숫자)
    info = await redis.xpending_range(STREAM_KEY, GROUP_NAME, min=message_id, max=message_id, count=1)
    times = info[0]["times_delivered"] if info else 1

    if times > MAX_DELIVERIES:
        # 받을 때마다 워커가 죽는 메시지 → 또 처리하면 또 죽으니까 처리하지 않고 치움
        logger.error("배달 %s번 넘음, dead-letter로: %s", times, message_id)
        await redis.xadd(
            DEAD_LETTER_KEY,
            {"message_id": message_id, "reason": "MAX_DELIVERIES_EXCEEDED", "payload": fields.get("payload", "")},
            maxlen=DEAD_LETTER_MAXLEN,
            approximate=True,
        )
        await redis.xack(STREAM_KEY, GROUP_NAME, message_id)
        # 결과를 기다리는 화면이 계속 "분석 중"에 멈추지 않게 FAILED를 알림 (payload가 깨졌으면 알릴 대상이 없어서 생략)
        try:
            task = TaskMessage.model_validate_json(fields.get("payload", ""))
            await redis.publish(RESULT_CHANNEL, json.dumps({**task.model_dump(mode="json"), "status": "FAILED"}))
        except ValidationError:
            pass
        # TODO 5단계: DB status = FAILED
        return

    await process_message(redis, message_id, fields)


async def claim_stuck(redis: Redis) -> None:
    """B. 다른 워커가 죽어서 CLAIM_IDLE_MS 넘게 멈춘 메시지를 내 것으로 가져와 처리."""
    # XAUTOCLAIM = "CLAIM_IDLE_MS 넘게 ACK 안 된 Pending 메시지를 찾아서 주인을 나로 바꿔 줘"
    # 돌려주는 값 3개: 다음에 이어서 찾을 위치, 가져온 메시지들, 그사이 스트림에서 지워진 id들 (Redis 7+)
    # 한 번에 10개만 가져오고 다음 위치는 버림 → 30초 뒤 처음(0-0)부터 다시 찾으니까 결국 다 처리됨
    _next_id, messages, _deleted = await redis.xautoclaim(
        STREAM_KEY,
        GROUP_NAME,
        CONSUMER_NAME,
        min_idle_time=CLAIM_IDLE_MS,
        start_id="0-0",
        count=10,
    )
    for message_id, fields in messages:
        logger.warning("멈춘 메시지 가져옴: %s", message_id)
        await handle_claimed(redis, message_id, fields)


async def recover_own_pending(redis: Redis) -> None:
    """A. 워커가 죽기 전에 가져갔지만 ACK 못 한 내 메시지를 다시 처리."""
    while True:
        # ">" 대신 "0" = "새 메시지 말고, 내가(CONSUMER_NAME) 가져갔는데 아직 ACK 안 한 메시지를 처음부터 줘"
        # block을 안 줘서 없으면 바로 빈 결과가 옴
        streams = await redis.xreadgroup(GROUP_NAME, CONSUMER_NAME, {STREAM_KEY: "0"}, count=10)
        if not streams or not streams[0][1]:
            break  # 내 Pending이 비었으면 끝
        # 처리한 메시지는 XACK돼서 Pending에서 빠짐 → 다음 바퀴엔 남은 것만 옴
        for message_id, fields in streams[0][1]:
            await handle_claimed(redis, message_id, fields)


async def main() -> None:
    redis = Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
    await ensure_group(redis)
    logger.info("워커 시작: %s", CONSUMER_NAME)
    await recover_own_pending(redis)  # A. 시작할 때 한 번: 죽기 전에 못 끝낸 내 메시지부터

    loop = asyncio.get_running_loop()
    last_claim = loop.time()  # 마지막으로 멈춘 메시지를 확인한 시각 (초)
    while True:
        # B. 30초마다 다른 워커가 놓친 메시지 확인
        # 아래 xreadgroup이 block=5000이라 메시지가 없어도 5초마다 여기로 돌아옴 → 확인이 밀리지 않음
        if loop.time() - last_claim >= CLAIM_EVERY_SEC:
            await claim_stuck(redis)
            last_claim = loop.time()

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
