"""11-1에서 확인된 건강·생활 기록을 내부 검색 신호로 변환한다."""

from datetime import date, datetime, time, timedelta
from typing import Any

from app.models.health_logs import HealthLog, HealthLogType
from app.repositories.health_log_repository import HealthLogRepository
from app.repositories.health_profile_repository import HealthProfileRepository
from shared.tasks import KST


def week_start(target_on: date) -> datetime:
    monday = target_on - timedelta(days=target_on.weekday())
    return datetime.combine(monday, time.min, tzinfo=KST)


async def _weekly_record(
    repo: HealthLogRepository, user_id: int, log_type: HealthLogType, current: datetime, end: datetime
) -> HealthLog | None:
    record = await repo.find_in_range(user_id, log_type, current, end)
    if record is None:
        record = await repo.find_in_range(user_id, log_type, current - timedelta(days=7), current)
    return record


async def gather_daily_action_facts(user_id: int, target_on: date) -> dict[str, Any]:
    """본인의 최신 설문과 종류별 KST 이번 주/지난주 기록을 사용한다."""
    facts: dict[str, Any] = {}
    profile = await HealthProfileRepository().get_latest(user_id)
    if profile is not None:
        facts["is_hypertension_diagnosed"] = profile.is_hypertension_diagnosed
        facts["is_diabetes_diagnosed"] = profile.is_diabetes_diagnosed
        # BS3_1: 매일 1, 가끔 2. 과거 3, 비해당 8 및 미확인 값은 양성 신호가 아니다.
        if profile.smoking_current in (1, 2):
            facts["is_current_smoker"] = True
        # BD1_11: 최근 1년 음주 있음 2~6. 전혀 없음 1, 비해당 8 제외.
        if profile.alcohol_ever == 2 and profile.alcohol_frequency in (2, 3, 4, 5, 6):
            facts["has_reported_alcohol"] = True

    current = week_start(target_on)
    end = min(
        current + timedelta(days=7),
        datetime.combine(target_on + timedelta(days=1), time.min, tzinfo=KST),
        datetime.now(KST),
    )
    if end <= current:
        return facts

    repo = HealthLogRepository()
    walk = await _weekly_record(repo, user_id, HealthLogType.WALK_DAYS, current, end)
    if walk is not None:
        if walk.value == 0:
            facts["has_zero_walk_days"] = True
        elif 1 <= walk.value <= 7:
            facts["has_walk_days"] = True

    strength = await _weekly_record(repo, user_id, HealthLogType.STRENGTH_DAYS, current, end)
    if strength is not None and 0 <= strength.value < 2:
        facts["has_fewer_strength_days"] = True

    sleep = await _weekly_record(repo, user_id, HealthLogType.SLEEP, current, end)
    if sleep is not None and sleep.value2 is not None and 0 <= sleep.value <= 24 and 0 <= sleep.value2 <= 24:
        facts["has_sleep_record"] = True

    # 0일은 실제 응답이다. 누락값을 0으로 바꾸거나 지난주의 양성 신호로 덮지 않는다.
    return facts
