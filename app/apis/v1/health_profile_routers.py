"""3장 건강 프로필(설문) API."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.dtos.health_profiles import HealthProfileCreateRequest
from app.models.health_profiles import SurveyKind
from app.models.users import User
from app.services.health_profiles import HealthProfileService

health_profile_router = APIRouter(prefix="/health-profiles", tags=["health-profiles"])


@health_profile_router.post("", status_code=status.HTTP_201_CREATED)
async def create_health_profile(
    data: HealthProfileCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
) -> ORJSONResponse:
    """3-1 설문 저장 (가입 설문·주간 재설문)."""
    return ORJSONResponse(await service.create(user, data), status_code=status.HTTP_201_CREATED)


@health_profile_router.get("/questions")
async def get_survey_questions(
    user: Annotated[User, Depends(get_request_user)],
    kind: Annotated[SurveyKind, Query()],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
) -> dict[str, Any]:
    """3-6 설문 문항 정의. kind가 ONBOARDING·WEEKLY가 아니면 422."""
    return await service.get_questions(user.id, kind)
