"""챌린지 주간 달성 수 공통 함수 테스트."""

from datetime import date

from app.services.challenge_progress import week_progress


def test_over_target():
    """목표를 초과해도 실제 체크 수는 유지한다."""
    week_start = date(2026, 11, 23)
    dates = [date(2026, 11, day) for day in range(23, 28)]

    assert week_progress(dates, week_start, 3) == (5, 3)


def test_other_weeks_excluded():
    """이번 주 이외의 체크는 계산하지 않는다."""
    week_start = date(2026, 11, 23)
    dates = [
        date(2026, 11, 22),
        date(2026, 11, 23),
        date(2026, 11, 29),
        date(2026, 11, 30),
    ]

    assert week_progress(dates, week_start, 3) == (2, 2)


def test_no_checks():
    """체크가 없으면 달성 수는 0이다."""
    assert week_progress([], date(2026, 11, 23), 3) == (0, 0)
