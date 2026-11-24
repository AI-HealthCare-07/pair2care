from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

STREAM_KEY = "ai:tasks"  # FastAPI가 XADD 하는 곳
GROUP_NAME = "ai-workers"  # 워커들의 Consumer Group
RESULT_CHANNEL = "ai:results"  # 끝나면 Pub/Sub으로 알리는 곳
KST = ZoneInfo("Asia/Seoul")
DEAD_LETTER_KEY = "ai:tasks:dead"  # 실패한 작업 모아두는 Stream


class TaskType(StrEnum):
    MEAL_CLASSIFY = "MEAL_CLASSIFY"  # 식단 분류
    RECOMMEND_LLM = "RECOMMEND_LLM"  # LLM 추천


class TaskMessage(BaseModel):
    task_id: str = Field(
        default_factory=lambda: str(uuid4())
    )  # UUID4 사용하여 동시 요청에도 중복되지 않는 고유 ID 자동 생성
    task_type: TaskType
    user_id: int
    target_id: int
    # MEAL_CLASSIFY: 식단 기록 테이블(meals)의 PK
    # RECOMMEND_LLM: 추천 요청 기록 테이블(recommendations)의 PK
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(KST)
    )  # datetime 타입 + 한국 시간(KST) 명시적 부여


class TaskResult(TaskMessage):
    """ai:results로 보내는 완료 알림: 작업 필드 그대로 + 결과 상태 (SSE task 이벤트와 같은 모양)."""

    status: Literal["COMPLETED", "FAILED"]  # SSE task 이벤트는 두 값만 알림 (api.md 11-6)
