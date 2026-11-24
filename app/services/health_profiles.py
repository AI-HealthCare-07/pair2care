"""3장 건강 프로필(설문) 서비스."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import status
from tortoise.transactions import in_transaction

from app.core import default_logger as logger
from app.core.exceptions import AppError, ErrorCode
from app.dtos.health_profiles import HealthProfileCreateRequest
from app.models.health_profiles import HealthProfile, SurveyKind
from app.models.users import User
from app.repositories.health_profile_repository import HealthProfileRepository, to_answer_values
from app.services.prediction.features import calculate_age
from app.services.prediction.plan import plan_predictions
from app.services.prediction.service import PredictionService, summarize
from app.services.survey.questions import QUESTIONS, SURVEY_VERSION, build_questions
from app.services.survey.validation import resolve_answers

KST = ZoneInfo("Asia/Seoul")

SURVEY_VERSION_MISMATCH_DETAIL = "설문 문항이 바뀌었어요. 다시 불러올게요."
ONBOARDING_REQUIRED_DETAIL = "가입 설문을 먼저 해 주세요."
ONBOARDING_ALREADY_DONE_DETAIL = "가입 설문은 이미 했어요. 바뀐 내용은 주간 설문에서 알려 주세요."


class HealthProfileService:
    def __init__(self) -> None:
        self.health_profile_repo = HealthProfileRepository()
        self.prediction_service = PredictionService()

    async def get_questions(self, user_id: int, kind: SurveyKind) -> dict[str, Any]:
        """3-6. ONBOARDING은 설문이 없어도 200, WEEKLY는 직전 행으로 ask_when_applicable을 채움."""
        if kind == SurveyKind.ONBOARDING:
            return build_questions(kind)

        latest = await self.health_profile_repo.get_latest(user_id)
        if latest is None:
            raise onboarding_required()
        return build_questions(kind, to_answer_values(latest))

    async def create(self, user: User, data: HealthProfileCreateRequest) -> dict[str, Any]:
        """3-1. 검사 순서: 형식 422(DTO) → 버전·순서 409 → 성별·문항 400 → 저장 201."""
        if data.survey_version != SURVEY_VERSION:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                detail=SURVEY_VERSION_MISMATCH_DETAIL,
                code=ErrorCode.SURVEY_VERSION_MISMATCH,
            )

        async with in_transaction() as conn:
            # 같은 사용자의 설문 저장을 한 줄로 세움 (가입 설문 두 번 동시 요청 등)
            await User.filter(id=user.id).using_db(conn).select_for_update().first()
            latest = await self.health_profile_repo.get_latest(user.id, using_db=conn)
            check_survey_order(data.kind, latest)

            previous = to_answer_values(latest) if latest is not None else None
            values = resolve_answers(data.kind, user.gender, data.answers(), previous)
            profile = await self.health_profile_repo.create(
                user_id=user.id,
                kind=data.kind,
                survey_version=data.survey_version,
                values=values,
                using_db=conn,
            )

        surveyed_on = profile.created_at.astimezone(KST).date()
        age = calculate_age(user.birthday, surveyed_on)
        plan = plan_predictions(
            age=age,
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )
        # 예측이 실패해도 설문은 이미 저장됨 → 다시 받게 하지 않고 prediction_error로 알림 (api.md 3-1 처리 순서 3)
        predictions: list[dict[str, Any]] = []
        prediction_error = False
        try:
            rows = await self.prediction_service.predict(user, profile, plan, age, surveyed_on)
            predictions = [summarize(row) for row in rows]
        except Exception:
            # 건강정보가 로그에 남지 않게 id만 남김
            logger.exception("예측 실패 health_profile_id=%s", profile.id)
            prediction_error = True

        return {
            "health_profile": serialize_profile(profile),
            "predictions": predictions,
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
            "prediction_error": prediction_error,
        }


def onboarding_required() -> AppError:
    return AppError(
        status_code=status.HTTP_409_CONFLICT,
        detail=ONBOARDING_REQUIRED_DETAIL,
        code=ErrorCode.ONBOARDING_REQUIRED,
    )


def check_survey_order(kind: SurveyKind, latest: HealthProfile | None) -> None:
    """가입 설문이 먼저, 한 번만. 행이 하나라도 있으면 가입 설문은 이미 한 것 (첫 행은 항상 ONBOARDING)."""
    if kind == SurveyKind.ONBOARDING and latest is not None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            detail=ONBOARDING_ALREADY_DONE_DETAIL,
            code=ErrorCode.ONBOARDING_ALREADY_DONE,
        )
    if kind == SurveyKind.WEEKLY and latest is None:
        raise onboarding_required()


def serialize_profile(profile: HealthProfile) -> dict[str, Any]:
    """응답 health_profile: 요청 필드 전부 + 서버가 채운 코드 (api.md 3-1 응답 201)."""
    body: dict[str, Any] = {
        "id": profile.id,
        "kind": profile.kind.value,
        "survey_version": profile.survey_version,
    }
    for question in QUESTIONS:
        value = getattr(profile, question["field"])
        body[question["field"]] = float(value) if isinstance(value, Decimal) else value
    body["created_at"] = to_kst_iso(profile.created_at)
    return body


def to_kst_iso(value: datetime) -> str:
    return value.astimezone(KST).isoformat()
