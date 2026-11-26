"""3장 건강 프로필(설문) API. 경로 순서: /questions·/latest를 /{profile_id}보다 먼저."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.dtos.health_profiles import HealthProfileCreateRequest
from app.models.health_profiles import SurveyKind
from app.models.users import User
from app.services.health_profiles import DEFAULT_LIMIT, MAX_LIMIT, HealthProfileService

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


@health_profile_router.get("/latest")
async def get_latest_health_profile(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
) -> dict[str, Any]:
    """3-2 최근 설문 (S-27 마이). 없으면 404."""
    return await service.get_latest(user)


@health_profile_router.get("")
async def list_health_profiles(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
    kind: Annotated[SurveyKind | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    """3-3 설문 이력 (최신순, kind 생략 시 전체)."""
    return await service.list_profiles(user, kind, limit, cursor)


@health_profile_router.get("/{profile_id}")
async def get_health_profile(
    profile_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthProfileService, Depends(HealthProfileService)],
) -> dict[str, Any]:
    """3-5 설문 한 건. 남의 것이면 404. /latest·/questions보다 뒤에 둬야 함 (경로가 먼저 맞는 쪽으로 감)."""
    return await service.get(user, profile_id)
