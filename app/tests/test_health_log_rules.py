"""6장 건강 기록 규칙 (api.md 6-0, DB 없이 도는 순수 테스트)."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.health_logs import HealthLogType as T
from app.services.health_log_rules import KST, RULES, check_daily_values, josa, resolve_measured_at, week_start_at


def detail_of(log_type: T, value: str, value2: str | None = None) -> str:
    with pytest.raises(HTTPException) as exc:
        check_daily_values(log_type, Decimal(value), Decimal(value2) if value2 is not None else None)
    assert exc.value.status_code == 400
    return str(exc.value.detail)


def test_every_type_has_rule_and_unit_matches_spec() -> None:
    assert set(RULES) == set(T)
    assert RULES[T.BLOOD_PRESSURE].unit == "mmHg"
    assert RULES[T.CONDITION].unit is None
    assert RULES[T.SLEEP].unit == "hours_per_day"
    assert {t for t, r in RULES.items() if r.is_weekly} == {
        T.WALK_DAYS,
        T.STRENGTH_DAYS,
        T.SITTING_HOURS,
        T.SLEEP,
        T.BREAKFAST,
        T.STRESS,
    }
    assert {t for t, r in RULES.items() if r.is_once_a_day} == {T.STEPS, T.CONDITION}


def test_valid_daily_values() -> None:
    check_daily_values(T.BLOOD_PRESSURE, Decimal("132"), Decimal("84"))
    check_daily_values(T.BLOOD_GLUCOSE, Decimal("132.0"), None)  # 소수점 0은 정수로 통과
    check_daily_values(T.WEIGHT, Decimal("70.4"), None)
    check_daily_values(T.ALCOHOL, Decimal("0"), None)
    check_daily_values(T.CONDITION, Decimal("2"), None)


def test_weekly_type_is_400() -> None:
    assert detail_of(T.WALK_DAYS, "3") == "주간 기록은 주간 기록 API로 저장해 주세요."


def test_blood_pressure_rules() -> None:
    assert detail_of(T.BLOOD_PRESSURE, "132") == "이완기 혈압도 같이 입력해 주세요."
    assert detail_of(T.BLOOD_PRESSURE, "84", "84") == "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."
    assert detail_of(T.BLOOD_PRESSURE, "270", "84") == "수축기 혈압은 60~260 사이로 입력해 주세요."
    assert detail_of(T.BLOOD_PRESSURE, "132", "20") == "이완기 혈압은 30~160 사이로 입력해 주세요."


def test_value2_only_for_two_value_types() -> None:
    assert detail_of(T.BLOOD_GLUCOSE, "100", "1") == "이 기록에는 두 번째 값을 넣을 수 없어요."


@pytest.mark.parametrize(
    ("log_type", "value", "detail"),
    [
        (T.WEIGHT, "70.25", "체중은 소수 첫째 자리까지 입력해 주세요."),
        (T.STEPS, "100.5", "걸음 수는 정수로 입력해 주세요."),
        (T.EXERCISE, "0", "운동 시간은 1~600 사이로 입력해 주세요."),
        (T.CONDITION, "3", "컨디션은 0~2 사이로 입력해 주세요."),
        (T.ALCOHOL, "50.5", "마신 잔 수는 0~50 사이로 입력해 주세요."),
    ],
)
def test_range_and_decimal_places(log_type: T, value: str, detail: str) -> None:
    assert detail_of(log_type, value) == detail


def test_measured_at() -> None:
    now = datetime(2026, 11, 25, 12, 0, tzinfo=KST)

    assert resolve_measured_at(None, now) == now
    assert resolve_measured_at(datetime(2026, 11, 25, 7, 40), now).tzinfo == KST  # 시간대 없으면 KST
    assert resolve_measured_at(now + timedelta(minutes=5), now) == now + timedelta(minutes=5)  # 5분 여유
    with pytest.raises(HTTPException) as exc:
        resolve_measured_at(now + timedelta(minutes=6), now)
    assert exc.value.detail == "아직 오지 않은 시각으로는 기록할 수 없어요."


def test_week_start() -> None:
    today = date(2026, 11, 25)  # 수요일, 이번 주 월요일 11/23
    this_monday, last_monday = date(2026, 11, 23), date(2026, 11, 16)

    assert week_start_at(this_monday, today, is_saving=True) == datetime(2026, 11, 23, tzinfo=KST)
    assert week_start_at(last_monday, today, is_saving=True).date() == last_monday
    assert week_start_at(date(2026, 11, 9), today, is_saving=False).date() == date(2026, 11, 9)  # 조회는 됨

    for bad, detail in [
        (date(2026, 11, 24), "주간 기록은 그 주 월요일 날짜로 보내 주세요."),
        (date(2026, 11, 9), "주간 기록은 이번 주와 지난주만 저장할 수 있어요."),
        (date(2026, 11, 30), "주간 기록은 이번 주와 지난주만 저장할 수 있어요."),
    ]:
        with pytest.raises(HTTPException) as exc:
            week_start_at(bad, today, is_saving=True)
        assert exc.value.detail == detail


def test_josa_follows_final_consonant() -> None:
    assert josa("혈압", "은", "는") == "혈압은"
    assert josa("걸음 수", "은", "는") == "걸음 수는"
    assert josa("체중", "을", "를") == "체중을"
    assert josa("컨디션", "을", "를") == "컨디션을"
