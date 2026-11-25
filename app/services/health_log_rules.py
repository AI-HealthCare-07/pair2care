"""6장 건강 기록 종류별 규칙 (api.md 6-0, 11/23 확정). DB 없이 쓰는 순수 함수, 위반이면 400.

종류마다 범위·소수점이 달라서 요청 형식(422)으로는 못 막고 여기서 400 + 종류별 문구로 막는다.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Final
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.models.health_logs import HealthLogType

KST: Final = ZoneInfo("Asia/Seoul")
FUTURE_GRACE: Final = timedelta(minutes=5)  # 기기 시계 차이 여유


@dataclass(frozen=True)
class ValueRule:
    label: str  # 문구용 이름
    minimum: Decimal
    maximum: Decimal
    decimal_places: int = 0  # 0 = 정수만


@dataclass(frozen=True)
class LogTypeRule:
    unit: str | None
    value: ValueRule
    value2: ValueRule | None = None  # 있으면 필수 (혈압 이완기, 주말 수면)
    is_weekly: bool = False
    is_once_a_day: bool = False  # 같은 날(KST) 다시 저장하면 덮어씀


def rule(label: str, minimum: str, maximum: str, decimal_places: int = 0) -> ValueRule:
    return ValueRule(label, Decimal(minimum), Decimal(maximum), decimal_places)


RULES: Final[dict[HealthLogType, LogTypeRule]] = {
    HealthLogType.BLOOD_PRESSURE: LogTypeRule(
        "mmHg", rule("수축기 혈압", "60", "260"), value2=rule("이완기 혈압", "30", "160")
    ),
    HealthLogType.BLOOD_GLUCOSE: LogTypeRule("mg/dL", rule("혈당", "40", "600")),
    HealthLogType.ALCOHOL: LogTypeRule("drinks", rule("마신 잔 수", "0", "50", decimal_places=1)),
    HealthLogType.EXERCISE: LogTypeRule("minutes", rule("운동 시간", "1", "600")),
    HealthLogType.STEPS: LogTypeRule("steps", rule("걸음 수", "0", "100000"), is_once_a_day=True),
    HealthLogType.CONDITION: LogTypeRule(None, rule("컨디션", "0", "2"), is_once_a_day=True),
    HealthLogType.WEIGHT: LogTypeRule("kg", rule("체중", "25", "300", decimal_places=1)),
    HealthLogType.WALK_DAYS: LogTypeRule("days_per_week", rule("걷기 날 수", "0", "7"), is_weekly=True),
    HealthLogType.STRENGTH_DAYS: LogTypeRule("days_per_week", rule("근력 운동 날 수", "0", "5"), is_weekly=True),
    HealthLogType.SITTING_HOURS: LogTypeRule(
        "hours_per_day", rule("앉아 있는 시간", "0", "24", decimal_places=1), is_weekly=True
    ),
    HealthLogType.SLEEP: LogTypeRule(
        "hours_per_day",
        rule("주중 수면 시간", "0", "24", decimal_places=1),
        value2=rule("주말 수면 시간", "0", "24", decimal_places=1),
        is_weekly=True,
    ),
    HealthLogType.BREAKFAST: LogTypeRule(None, rule("아침 식사", "0", "3"), is_weekly=True),
    HealthLogType.STRESS: LogTypeRule(None, rule("스트레스", "0", "3"), is_weekly=True),
}

WEEKLY_ONLY_DETAIL: Final = "주간 기록은 주간 기록 API로 저장해 주세요."
NO_VALUE2_DETAIL: Final = "이 기록에는 두 번째 값을 넣을 수 없어요."
BLOOD_PRESSURE_DETAIL: Final = "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."
FUTURE_TIME_DETAIL: Final = "아직 오지 않은 시각으로는 기록할 수 없어요."
NOT_MONDAY_DETAIL: Final = "주간 기록은 그 주 월요일 날짜로 보내 주세요."
WEEK_NOT_EDITABLE_DETAIL: Final = "주간 기록은 이번 주와 지난주만 저장할 수 있어요."


def josa(word: str, with_final: str, without_final: str) -> str:
    """받침에 맞는 조사 ("혈압은", "걸음 수는"). 한글이 아니면 받침 없는 쪽."""
    last = word[-1]
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return word + with_final
    return word + without_final


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def check_value(value_rule: ValueRule, value: Decimal) -> None:
    if not value_rule.minimum <= value <= value_rule.maximum:
        raise bad_request(
            f"{josa(value_rule.label, '은', '는')} {value_rule.minimum}~{value_rule.maximum} 사이로 입력해 주세요."
        )
    # 허용 자릿수로 반올림했을 때 값이 바뀌면 자릿수 초과 (132.0은 정수로 통과, 70.25는 체중에서 걸림)
    if value != value.quantize(Decimal(1).scaleb(-value_rule.decimal_places)):
        places = "정수로" if value_rule.decimal_places == 0 else "소수 첫째 자리까지"
        raise bad_request(f"{josa(value_rule.label, '은', '는')} {places} 입력해 주세요.")


def check_daily_values(log_type: HealthLogType, value: Decimal, value2: Decimal | None) -> None:
    """일일 기록 값 (6-1·6-3). 주간 종류는 400, 범위·소수점·두 번째 값·혈압 순서."""
    type_rule = RULES[log_type]
    if type_rule.is_weekly:
        raise bad_request(WEEKLY_ONLY_DETAIL)
    check_value(type_rule.value, value)
    if type_rule.value2 is None:
        if value2 is not None:
            raise bad_request(NO_VALUE2_DETAIL)
        return
    if value2 is None:
        raise bad_request(f"{type_rule.value2.label}도 같이 입력해 주세요.")
    check_value(type_rule.value2, value2)
    if log_type == HealthLogType.BLOOD_PRESSURE and value <= value2:
        raise bad_request(BLOOD_PRESSURE_DETAIL)


def resolve_measured_at(measured_at: datetime | None, now: datetime) -> datetime:
    """생략하면 지금. 시간대가 없으면 KST로 봄. 5분 넘게 미래면 400."""
    if measured_at is None:
        return now
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=KST)
    if measured_at > now + FUTURE_GRACE:
        raise bad_request(FUTURE_TIME_DETAIL)
    return measured_at


def kst_day_range(day: date) -> tuple[datetime, datetime]:
    """KST 하루 [00:00, 다음 날 00:00)."""
    start = datetime.combine(day, time.min, tzinfo=KST)
    return start, start + timedelta(days=1)


def week_start_at(week_start: date, today: date, *, is_saving: bool) -> datetime:
    """주간 기록 measured_at = 그 주 월요일 00:00 KST. 저장은 이번 주·지난주만."""
    if week_start.weekday() != 0:
        raise bad_request(NOT_MONDAY_DETAIL)
    if is_saving:
        this_monday = today - timedelta(days=today.weekday())
        if week_start not in (this_monday, this_monday - timedelta(days=7)):
            raise bad_request(WEEK_NOT_EDITABLE_DETAIL)
    return datetime.combine(week_start, time.min, tzinfo=KST)
