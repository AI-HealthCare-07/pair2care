"""데모용 가상 사용자 시드 (12/30 데모데이 시나리오, REQ 시나리오 2 "고혈압 주의 → 습관 개선 → 추이 확인").

**가상 데이터만** 넣음 (실제 사람·국건영 원본 아님). 로컬·스테이징 전용이라 ENV=prod면 실행하지 않음.

실행 (레포 루트, MySQL이 떠 있고 aerich upgrade를 마친 상태):
    DEMO_PASSWORD='원하는 비밀번호' DB_HOST=localhost uv run --env-file envs/.local.env python -m scripts.seed_demo

- 같은 이메일의 데모 사용자가 있으면 지우고 다시 만듦 (몇 번 돌려도 결과가 같음)
- 비밀번호는 DEMO_PASSWORD 환경 변수로만 받음 (레포가 공개라 코드에 두지 않음, 없으면 멈춤)
- 설문·검진은 서비스(3-1·4-1)로 저장해서 실제 모델로 예측한 뒤, 저장 시각만 과거로 옮김
- 건강 기록은 4주치를 바로 넣음 (6-4 주간 기록은 API로는 이번 주·지난주만 저장돼서)
"""

import asyncio
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Final

from tortoise import Tortoise

from app.core import config
from app.core import default_logger as logger
from app.core.config import Env
from app.core.db.databases import TORTOISE_ORM
from app.dtos.auth import ConsentItem, SignUpRequest
from app.dtos.checkup_records import CheckupRecordCreateRequest
from app.dtos.health_profiles import HealthProfileCreateRequest
from app.models.checkup_records import CheckupRecord
from app.models.health_logs import HealthLog, HealthLogType
from app.models.health_profiles import HealthProfile, SurveyKind
from app.models.risk_predictions import RiskPrediction
from app.models.user_consents import Agreement
from app.models.users import Gender, User
from app.services.auth import AuthService
from app.services.checkup_records import CheckupRecordService
from app.services.health_log_rules import KST, RULES
from app.services.health_profiles import HealthProfileService
from app.services.survey.questions import SURVEY_VERSION, WEEKLY_FIELDS

DEMO_EMAIL: Final = "demo@example.com"  # 예약 도메인 (실제로 등록될 수 없는 주소)
WEEKS: Final = 4
RANDOM_SEED: Final = 42

# 52세 남성, 아버지 고혈압, 매일 흡연, 주 2~3회·한 번에 5~6잔 → 4주 동안 체중·술·담배를 줄임
ONBOARDING_ANSWERS: Final[dict[str, Any]] = {
    "height_cm": 172.0,
    "weight_kg": 84.0,
    "waist_cm": 94.0,
    "father_diabetes_history": 0,
    "mother_diabetes_history": 0,
    "sibling_diabetes_history": 0,
    "father_hypertension_history": 1,
    "mother_hypertension_history": 0,
    "sibling_hypertension_history": 0,
    "alcohol_ever": 2,
    "alcohol_frequency": 4,  # 주 2~3회
    "alcohol_amount": 3,  # 5~6잔
    "binge_frequency": 3,
    "smoking_lifetime": 2,
    "smoking_current": 1,  # 매일
    "cigarettes_per_day": 10,
    "heated_tobacco": 8,
    "liquid_ecig": 8,
    "is_hypertension_diagnosed": False,
    "is_diabetes_diagnosed": False,
    "is_pregnant": None,
}

# 주 1회 재설문 (며칠 전, 바뀐 답). 묻지 않는 문항은 직전 설문에서 복사됨 (3-1 WEEKLY)
WEEKLY_CHANGES: Final[list[tuple[int, dict[str, Any]]]] = [
    (21, {"weight_kg": 83.0, "alcohol_frequency": 4, "alcohol_amount": 2, "binge_frequency": 2}),
    (14, {"weight_kg": 81.8, "alcohol_frequency": 3, "alcohol_amount": 2, "binge_frequency": 1}),
    (7, {"weight_kg": 80.6, "alcohol_frequency": 3, "alcohol_amount": 2, "binge_frequency": 1, "smoking_current": 3}),
    (0, {"weight_kg": 79.5, "alcohol_frequency": 2, "alcohol_amount": 1, "binge_frequency": 1, "smoking_current": 3}),
]
ONBOARDING_DAYS_AGO: Final = 28
CHECKUP_DAYS_AGO: Final = 26
CHECKUP_VALUES: Final[dict[str, Any]] = {
    "systolic_bp": 136,
    "diastolic_bp": 86,
    "fasting_glucose": 104,  # 공복혈당장애(100~125) → 당뇨 기준표도 "주의" (설문 모델 높음과 같은 방향)
    "waist_cm": 94.0,
}


@dataclass(frozen=True)
class SeedSummary:
    user_id: int
    health_profiles: int
    risk_predictions: int
    health_logs: int


def at_days_ago(now: datetime, days_ago: int, hour: int = 9) -> datetime:
    """며칠 전 그날 hour시 KST. 오늘(0)은 지금보다 늦지 않게."""
    moment = datetime.combine((now - timedelta(days=days_ago)).date(), time(hour), tzinfo=KST)
    return min(moment, now)


def weekly_request(changes: dict[str, Any], previous: dict[str, Any]) -> HealthProfileCreateRequest:
    """WEEKLY는 재설문 문항만 보냄. 담배를 끊으면 하루 개비 수는 건너뛰기라 안 보냄."""
    answers = {field: changes.get(field, previous.get(field)) for field in WEEKLY_FIELDS}
    if answers.get("smoking_current") == 3:
        answers["cigarettes_per_day"] = None
    return HealthProfileCreateRequest(kind=SurveyKind.WEEKLY, survey_version=SURVEY_VERSION, **answers)


async def move_new_rows(user: User, since_prediction_id: int, moment: datetime) -> None:
    """방금 만든 예측 행들의 시각을 과거로 (설문·검진 저장 시각과 같게)."""
    await RiskPrediction.filter(user_id=user.id, id__gt=since_prediction_id).update(created_at=moment)


async def last_prediction_id(user: User) -> int:
    row = await RiskPrediction.filter(user_id=user.id).order_by("-id").first()
    return row.id if row else 0


async def create_user(password: str, birthday: date) -> User:
    consents = [
        ConsentItem(agreement=agreement, is_agreed=True, version=config.TERMS_VERSION) for agreement in Agreement
    ]
    request = SignUpRequest(
        email=DEMO_EMAIL,
        password=password,
        nickname="데모 사용자",
        gender=Gender.MALE,
        birthday=birthday,
        consents=consents,
    )
    return await AuthService().signup(request)


async def seed_surveys(user: User, now: datetime) -> None:
    """가입 설문 → 검진 → 재설문 4번. 저장할 때마다 시각을 과거로 옮김 (설문 순서 검사는 시각이 아닌 종류만 봄)."""
    surveys = HealthProfileService()
    before = await last_prediction_id(user)
    onboarding = HealthProfileCreateRequest(
        kind=SurveyKind.ONBOARDING, survey_version=SURVEY_VERSION, **ONBOARDING_ANSWERS
    )
    created = await surveys.create(user, onboarding)
    moment = at_days_ago(now, ONBOARDING_DAYS_AGO)
    await HealthProfile.filter(id=created["health_profile"]["id"]).update(created_at=moment)
    await move_new_rows(user, before, moment)

    before = await last_prediction_id(user)
    checkup_on = (now - timedelta(days=CHECKUP_DAYS_AGO)).date()
    checkup = await CheckupRecordService().create(
        user, CheckupRecordCreateRequest(checked_on=checkup_on, **CHECKUP_VALUES)
    )
    moment = at_days_ago(now, CHECKUP_DAYS_AGO, hour=19)
    await CheckupRecord.filter(id=checkup["checkup_record"]["id"]).update(created_at=moment)
    await move_new_rows(user, before, moment)

    previous = dict(ONBOARDING_ANSWERS)
    for days_ago, changes in WEEKLY_CHANGES:
        before = await last_prediction_id(user)
        created = await surveys.create(user, weekly_request(changes, previous))
        moment = at_days_ago(now, days_ago, hour=8)
        await HealthProfile.filter(id=created["health_profile"]["id"]).update(created_at=moment)
        await move_new_rows(user, before, moment)
        previous.update(changes)


def daily_logs(user: User, now: datetime, rng: random.Random) -> list[HealthLog]:
    """4주치 일일 기록: 걸음 수·혈압·체중이 조금씩 좋아짐 (가상 값, 약간의 흔들림)."""
    logs: list[HealthLog] = []
    days = WEEKS * 7
    for days_ago in range(days, -1, -1):
        progress = (days - days_ago) / days  # 0 → 1
        day = (now - timedelta(days=days_ago)).date()

        def at(hour: int, minute: int = 0, *, on_day: date = day) -> datetime:
            return min(datetime.combine(on_day, time(hour, minute), tzinfo=KST), now)

        steps = round(4200 + 4600 * progress + rng.randint(-900, 900))
        logs.append(make_log(user, HealthLogType.STEPS, steps, at(21)))
        logs.append(
            make_log(
                user, HealthLogType.CONDITION, rng.choices([0, 1, 2], weights=[2, 5, 3 + 4 * progress])[0], at(21, 5)
            )
        )
        if days_ago % 2 == 0:
            systolic = round(142 - 12 * progress + rng.randint(-3, 3))
            diastolic = round(92 - 8 * progress + rng.randint(-2, 2))
            logs.append(make_log(user, HealthLogType.BLOOD_PRESSURE, systolic, at(7, 30), value2=diastolic))
        if days_ago % 7 == 0:
            weight = round(84.0 - 4.5 * progress + rng.uniform(-0.2, 0.2), 1)
            logs.append(make_log(user, HealthLogType.WEIGHT, weight, at(7, 40)))
        if rng.random() < 0.4 - 0.25 * progress:
            logs.append(make_log(user, HealthLogType.ALCOHOL, rng.choice([2, 3, 4, 5]) - round(2 * progress), at(22)))
        if rng.random() < 0.2 + 0.4 * progress:
            logs.append(make_log(user, HealthLogType.EXERCISE, rng.choice([20, 30, 40]), at(19)))
    return logs


def weekly_logs(user: User, now: datetime) -> list[HealthLog]:
    """주간 기록 6종, 4주 (measured_at = 그 주 월요일 00:00 KST, 6-4)."""
    this_monday = now.date() - timedelta(days=now.weekday())
    logs: list[HealthLog] = []
    for week in range(WEEKS):
        monday = datetime.combine(this_monday - timedelta(days=7 * (WEEKS - 1 - week)), time.min, tzinfo=KST)
        logs += [
            make_log(user, HealthLogType.WALK_DAYS, 2 + week, monday),
            make_log(user, HealthLogType.STRENGTH_DAYS, min(week, 2), monday),
            make_log(user, HealthLogType.SITTING_HOURS, 9 - week, monday),
            make_log(user, HealthLogType.SLEEP, 6, monday, value2=7.5),
            make_log(user, HealthLogType.BREAKFAST, min(1 + week, 3), monday),
            make_log(user, HealthLogType.STRESS, max(2 - week // 2, 1), monday),
        ]
    return logs


def make_log(
    user: User, log_type: HealthLogType, value: float, measured_at: datetime, value2: float | None = None
) -> HealthLog:
    return HealthLog(
        user_id=user.id,
        log_type=log_type,
        value=Decimal(str(value)),
        value2=Decimal(str(value2)) if value2 is not None else None,
        unit=RULES[log_type].unit,
        measured_at=measured_at,
    )


async def seed(now: datetime, password: str) -> SeedSummary:
    await User.filter(email=DEMO_EMAIL).delete()  # 관련 행은 CASCADE로 같이 지워짐
    user = await create_user(password, birthday=date(now.year - 52, 3, 15))
    await seed_surveys(user, now)
    rng = random.Random(RANDOM_SEED)
    await HealthLog.bulk_create(daily_logs(user, now, rng) + weekly_logs(user, now))
    return SeedSummary(
        user_id=user.id,
        health_profiles=await HealthProfile.filter(user_id=user.id).count(),
        risk_predictions=await RiskPrediction.filter(user_id=user.id).count(),
        health_logs=await HealthLog.filter(user_id=user.id).count(),
    )


def read_demo_password() -> str:
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        raise SystemExit("DEMO_PASSWORD 환경 변수가 없어요. 데모 계정 비밀번호를 정해서 같이 넘겨 주세요.")
    return password


async def main() -> None:
    if config.ENV == Env.PROD:
        raise SystemExit("ENV=prod에서는 데모 시드를 넣지 않아요.")
    password = read_demo_password()
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        summary = await seed(datetime.now(KST), password)
    finally:
        await Tortoise.close_connections()
    logger.info(
        "데모 사용자 %s 준비 완료: 설문 %d개, 예측 %d행, 건강 기록 %d행",
        DEMO_EMAIL,
        summary.health_profiles,
        summary.risk_predictions,
        summary.health_logs,
    )


if __name__ == "__main__":
    asyncio.run(main())
