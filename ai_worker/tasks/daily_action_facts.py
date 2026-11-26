"""11-1에서 확인된 건강·생활 기록을 내부 검색 신호로 변환한다."""

from datetime import date, datetime, time, timedelta
from typing import Any

from app.models.health_logs import HealthLogType
from app.repositories.health_log_repository import HealthLogRepository
from app.repositories.health_profile_repository import HealthProfileRepository
from shared.tasks import KST


def week_start(target_on: date) -> datetime:
    monday = target_on - timedelta(days=target_on.weekday())
    return datetime.combine(monday, time.min, tzinfo=KST)


async def gather_daily_action_facts(user_id: int, target_on: date) -> dict[str, Any]:
    """최신 설문과 KST 이번 주/지난주 걷기 기록만 사용한다."""
    facts: dict[str, Any] = {}
    profile = await HealthProfileRepository().get_latest(user_id)
    if profile is not None:
        facts["is_hypertension_diagnosed"] = profile.is_hypertension_diagnosed
        facts["is_diabetes_diagnosed"] = profile.is_diabetes_diagnosed
        # BS3_1: 매일 1, 가끔 2. 과거 3, 비해당 8 및 미확인 값은 양성 신호가 아니다.
        if profile.smoking_current in (1, 2):
            facts["is_current_smoker"] = True

    current = week_start(target_on)
    end = min(
        current + timedelta(days=7),
        datetime.combine(target_on + timedelta(days=1), time.min, tzinfo=KST),
        datetime.now(KST),
    )
    if end <= current:
        return facts

    repo = HealthLogRepository()
    walk = await repo.find_in_range(user_id, HealthLogType.WALK_DAYS, current, end)
    if walk is None:
        walk = await repo.find_in_range(user_id, HealthLogType.WALK_DAYS, current - timedelta(days=7), current)

    # 0일은 실제 응답이다. 누락값을 0으로 바꾸거나 지난주의 양성 신호로 덮지 않는다.
    if walk is not None and walk.value == 0:
        facts["has_zero_walk_days"] = True
    return facts
