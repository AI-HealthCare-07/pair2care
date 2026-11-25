"""6장 건강 기록 요청 (api.md 6-1·6-3·6-4). 종류별 범위·소수점은 서비스(health_log_rules)가 400으로 봄."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.models.health_logs import HealthLogType

Memo = Annotated[str, Field(max_length=500)]


class HealthLogCreateRequest(BaseModel):
    """unit은 서버가 종류에 맞게 채움 → 보내도 무시."""

    log_type: HealthLogType
    value: Decimal
    value2: Decimal | None = None
    measured_at: datetime | None = None  # 생략하면 지금
    memo: Memo | None = None


class HealthLogUpdateRequest(BaseModel):
    """보낸 필드만 바꿈. log_type은 못 바꿈 (보내면 400, 지우고 새로 저장)."""

    log_type: HealthLogType | None = None
    value: Decimal | None = None
    value2: Decimal | None = None
    measured_at: datetime | None = None
    memo: Memo | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, exclude={"log_type"})


Hours = Annotated[Decimal, Field(ge=0, le=24, max_digits=3, decimal_places=1)]


class WeeklyLogRequest(BaseModel):
    """6-4. 모두 선택, 보낸 항목만 저장·덮어씀, null이면 그 항목 삭제. 범위 밖은 422."""

    walk_days: Annotated[int, Field(ge=0, le=7)] | None = None
    strength_days: Annotated[int, Field(ge=0, le=5)] | None = None  # 5 = 5일 이상
    sitting_hours: Hours | None = None
    sleep_weekday_hours: Hours | None = None
    sleep_weekend_hours: Hours | None = None
    breakfast: Annotated[int, Field(ge=0, le=3)] | None = None
    stress: Annotated[int, Field(ge=0, le=3)] | None = None

    def sent(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)
