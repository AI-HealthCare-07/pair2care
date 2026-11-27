"""챌린지 주간 체크 수와 목표 달성 수 계산."""

from collections.abc import Iterable
from datetime import date, timedelta


def week_progress(
    checked_dates: Iterable[date],
    week_start: date,
    target: int,
) -> tuple[int, int]:
    """실제 체크 수(checked)와 목표 반영 수(filled)를 반환한다."""
    week_end = week_start + timedelta(days=7)
    checked = sum(week_start <= day < week_end for day in checked_dates)
    filled = min(checked, target)
    return checked, filled
