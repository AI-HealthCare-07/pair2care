"""3장 건강 프로필(설문) 서비스."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import status
from tortoise.transactions import in_transaction

from app.core.exceptions import AppError, ErrorCode
from app.dtos.health_profiles import HealthProfileCreateRequest
from app.models.health_profiles import HealthProfile, SurveyKind
from app.models.users import User
from app.repositories.health_profile_repository import HealthProfileRepository, to_answer_values
from app.services.prediction.features import calculate_age
from app.services.prediction.plan import plan_predictions
from app.services.survey.questions import QUESTIONS, SURVEY_VERSION, build_questions
from app.services.survey.validation import resolve_answers

KST = ZoneInfo("Asia/Seoul")

SURVEY_VERSION_MISMATCH_DETAIL = "설문 문항이 바뀌었어요. 다시 불러올게요."
ONBOARDING_REQUIRED_DETAIL = "가입 설문을 먼저 해 주세요."
ONBOARDING_ALREADY_DONE_DETAIL = "가입 설문은 이미 했어요. 바뀐 내용은 주간 설문에서 알려 주세요."


class HealthProfileService:
    def __init__(self) -> None:
        self.health_profile_repo = HealthProfileRepository()

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

        # 예측 행 저장(5-0)은 risk_predictions 모델과 같이 붙임. 지금은 어떤 질환을 예측할지까지만
        age = calculate_age(user.birthday, profile.created_at.astimezone(KST).date())
        plan = plan_predictions(
            age=age,
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )
        return {
            "health_profile": serialize_profile(profile),
            "predictions": [],
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
            "prediction_error": False,
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
