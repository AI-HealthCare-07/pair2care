"""3장 건강 프로필(설문) 서비스."""

from typing import Any

from fastapi import status

from app.core.exceptions import AppError, ErrorCode
from app.models.health_profiles import SurveyKind
from app.repositories.health_profile_repository import HealthProfileRepository, to_answer_values
from app.services.survey.questions import build_questions

ONBOARDING_REQUIRED_DETAIL = "가입 설문을 먼저 해 주세요."


class HealthProfileService:
    def __init__(self) -> None:
        self.health_profile_repo = HealthProfileRepository()

    async def get_questions(self, user_id: int, kind: SurveyKind) -> dict[str, Any]:
        """3-6. ONBOARDING은 설문이 없어도 200, WEEKLY는 직전 행으로 ask_when_applicable을 채움."""
        if kind == SurveyKind.ONBOARDING:
            return build_questions(kind)

        latest = await self.health_profile_repo.get_latest(user_id)
        if latest is None:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                detail=ONBOARDING_REQUIRED_DETAIL,
                code=ErrorCode.ONBOARDING_REQUIRED,
            )
        return build_questions(kind, to_answer_values(latest))
