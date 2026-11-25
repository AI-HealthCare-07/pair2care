"""7장 대시보드 서비스 (api.md 7-1~7-3, S-18·S-12)."""

from datetime import date, datetime, time, timedelta
from typing import Any, Final

from app.models.health_logs import HealthLogType
from app.models.health_profiles import HealthProfile
from app.models.risk_predictions import Disease, PredictionMethod, RiskPrediction
from app.models.users import User
from app.repositories.health_log_repository import HealthLogRepository
from app.repositories.health_profile_repository import HealthProfileRepository
from app.repositories.risk_prediction_repository import RiskPredictionRepository
from app.services.dashboard_rules import (
    DISEASE_ORDER,
    bucket_logs,
    build_risk_trend,
    choose_priority_disease,
    is_newer,
    monday_of,
    summarize_week_logs,
)
from app.services.health_log_rules import KST, RULES, bad_request, kst_day_range

UNKNOWN_TYPE_DETAIL: Final = "알 수 없는 기록 종류예요."
WEEKLY_TYPE_DETAIL: Final = "주간 기록은 주간 기록 API로 조회해 주세요."
DATE_ORDER_DETAIL: Final = "시작 날짜가 끝 날짜보다 늦어요."
TOO_LONG_DETAIL: Final = "한 번에 366일까지 조회할 수 있어요."
TOO_MANY_DETAIL: Final = "기록이 너무 많아요. 기간을 줄이거나 day·week로 묶어 주세요."
NOT_MONDAY_DETAIL: Final = "week_start는 그 주 월요일 날짜로 보내 주세요."

MAX_RANGE_DAYS: Final = 366
MAX_RAW_POINTS: Final = 1000  # raw는 6-2와 같은 한도
MAX_BUCKET_ROWS: Final = 20000  # 묶을 때는 점이 줄어서 넉넉히 (하루 50번 × 366일 정도)
WEEKLY_TYPES: Final = [log_type for log_type, rule in RULES.items() if rule.is_weekly]


class DashboardService:
    def __init__(self) -> None:
        self.prediction_repo = RiskPredictionRepository()
        self.profile_repo = HealthProfileRepository()
        self.log_repo = HealthLogRepository()

    async def risk_trend(self, user: User, weeks: int) -> dict[str, Any]:
        """7-1. 최근 N주(이번 주 포함), 질환별 주마다 마지막 MODEL 예측 1개."""
        start_monday = monday_of(today_kst()) - timedelta(weeks=weeks - 1)
        rows = await self.prediction_repo.list_since(user.id, at_midnight(start_monday))
        managed = managed_diseases(await self.profile_repo.get_latest(user.id))
        return {"series": build_risk_trend(rows, managed)}

    async def logs(self, user: User, raw_type: str, start_on: date, end_on: date, bucket: str) -> dict[str, Any]:
        """7-2. 집에서 잰 값(health_logs)만, 검진 수치는 섞지 않음. bucket raw·day·week."""
        log_type = parse_daily_type(raw_type)
        if start_on > end_on:
            raise bad_request(DATE_ORDER_DETAIL)
        if (end_on - start_on).days + 1 > MAX_RANGE_DAYS:
            raise bad_request(TOO_LONG_DETAIL)
        start, _ = kst_day_range(start_on)
        _, end = kst_day_range(end_on)
        limit = MAX_RAW_POINTS if bucket == "raw" else MAX_BUCKET_ROWS
        rows = await self.log_repo.list_in_range(user.id, [log_type], start, end, limit + 1)
        if len(rows) > limit:
            raise bad_request(TOO_MANY_DETAIL)
        return {
            "log_type": log_type.value,
            "unit": RULES[log_type].unit,
            "bucket": bucket,
            "points": bucket_logs(rows, log_type, bucket),
        }

    async def summary(self, user: User, week_start: date | None) -> dict[str, Any]:
        """7-3. 대시보드 첫 화면 한 번에. week_start 생략 시 이번 주."""
        if week_start is None:
            week_start = monday_of(today_kst())
        if week_start.weekday() != 0:
            raise bad_request(NOT_MONDAY_DETAIL)

        profile = await self.profile_repo.get_latest(user.id)
        managed = managed_diseases(profile)
        latest_rows = await self.latest_model_rows(profile)

        week_from = at_midnight(week_start)
        week_logs = await self.log_repo.list_in_range(
            user.id, list(HealthLogType), week_from, week_from + timedelta(days=7), MAX_BUCKET_ROWS
        )
        weekly_rows = await self.log_repo.list_at(user.id, WEEKLY_TYPES, week_from)
        priority = choose_priority_disease(latest_rows, managed)

        return {
            "week_start": week_start.isoformat(),
            "priority_disease": priority.value if priority else None,
            "latest_risk": [
                {
                    "disease": row.disease.value,
                    "score": row.score,
                    "level": row.level.value,
                    "created_at": row.created_at.astimezone(KST).isoformat(),
                }
                for row in latest_rows
            ],
            "managed_diseases": [disease.value for disease in managed],
            "logs": summarize_week_logs(week_logs),
            "weekly_record_done": bool(weekly_rows),
            "challenge": None,  # 8장 챌린지가 머지되면 이번 주 체크 수 ÷ 목표 횟수로 채움 (이지희와 계산식 맞춤)
            "meal": None,  # 식단(P2)이 붙으면 { kcal_avg, sodium_avg_mg }
        }

    async def latest_model_rows(self, profile: HealthProfile | None) -> list[RiskPrediction]:
        """최근 설문에 연결된 질환별 최신 MODEL 행 (5-2와 같은 기준), 당뇨 → 고혈압 순서."""
        if profile is None:
            return []
        latest: dict[Disease, RiskPrediction] = {}
        for row in await self.prediction_repo.list_for_profile(profile.id):
            if row.method != PredictionMethod.MODEL:
                continue
            current = latest.get(row.disease)
            if current is None or is_newer(row, current):
                latest[row.disease] = row
        return [latest[disease] for disease in DISEASE_ORDER if disease in latest]


def today_kst() -> date:
    return datetime.now(KST).date()


def at_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=KST)


def managed_diseases(profile: HealthProfile | None) -> list[Disease]:
    """최근 설문에서 진단 "예"인 질환 (관리 중 카드)."""
    if profile is None:
        return []
    diagnosed = {
        Disease.DIABETES: profile.is_diabetes_diagnosed,
        Disease.HYPERTENSION: profile.is_hypertension_diagnosed,
    }
    return [disease for disease in DISEASE_ORDER if diagnosed[disease]]


def parse_daily_type(raw: str) -> HealthLogType:
    try:
        log_type = HealthLogType(raw.strip())
    except ValueError:
        raise bad_request(UNKNOWN_TYPE_DETAIL) from None
    if RULES[log_type].is_weekly:
        raise bad_request(WEEKLY_TYPE_DETAIL)
    return log_type
