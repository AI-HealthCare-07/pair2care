"""3장 건강 프로필(설문) API."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.dependencies.security import get_request_user
from app.models.health_profiles import SurveyKind
from app.models.users import User
from app.services.health_profiles import HealthProfileService

health_profile_router = APIRouter(prefix="/health-profiles", tags=["health-profiles"])


@health_profile_router.get("/questions")
async def get_survey_questions(
    user: Annotated[User, Depends(get_request_user)],
    kind: Annotated[SurveyKind, Query()],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
) -> dict[str, Any]:
    """3-6 설문 문항 정의. kind가 ONBOARDING·WEEKLY가 아니면 422."""
    return await service.get_questions(user.id, kind)
