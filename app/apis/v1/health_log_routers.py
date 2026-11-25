"""6장 건강 기록 API (S-19 일일 기록, S-11 주간 기록, S-12 컨디션)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.dtos.health_logs import HealthLogCreateRequest, HealthLogUpdateRequest, WeeklyLogRequest
from app.models.users import User
from app.services.health_logs import HealthLogService

health_log_router = APIRouter(prefix="/health-logs", tags=["health-logs"])


@health_log_router.post("", status_code=status.HTTP_201_CREATED)
async def create_health_log(
    data: HealthLogCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
) -> ORJSONResponse:
    """6-1 일일 기록. 걸음 수·컨디션은 같은 날이 있으면 덮어쓰고 200."""
    body, is_created = await service.create(user, data)
    return ORJSONResponse(body, status_code=status.HTTP_201_CREATED if is_created else status.HTTP_200_OK)


@health_log_router.get("")
async def list_health_logs(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
    log_type: Annotated[str, Query(description="여러 개는 쉼표 (BLOOD_PRESSURE,WEIGHT)")],
    start_on: Annotated[date, Query(alias="from")],
    end_on: Annotated[date, Query(alias="to")],
) -> dict[str, Any]:
    """6-2 기록 조회 (그래프용, 오래된 순)."""
    return await service.list_logs(user, log_type, start_on, end_on)


@health_log_router.put("/weekly/{week_start}")
async def put_weekly_logs(
    week_start: date,
    data: WeeklyLogRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
) -> dict[str, Any]:
    """6-4 주간 기록 저장 (이번 주·지난주만)."""
    return await service.put_weekly(user, week_start, data)


@health_log_router.get("/weekly/{week_start}")
async def get_weekly_logs(
    week_start: date,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
) -> dict[str, Any]:
    """6-5 주간 기록 조회. 없는 항목은 null."""
    return await service.get_weekly(user, week_start)


@health_log_router.patch("/{log_id}")
async def update_health_log(
    log_id: int,
    data: HealthLogUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
) -> dict[str, Any]:
    """6-3 수정 (보낸 필드만)."""
    return await service.update(user, log_id, data)


@health_log_router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_health_log(
    log_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[HealthLogService, Depends(HealthLogService)],
) -> Response:
    """6-3 삭제."""
    await service.delete(user, log_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
