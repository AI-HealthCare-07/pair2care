"""7장 대시보드 API (S-18, S-12 일부)."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies.security import get_request_user
from app.models.users import User
from app.services.dashboard import DashboardService

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("/risk-trend")
async def get_risk_trend(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[DashboardService, Depends(DashboardService)],
    weeks: Annotated[int, Query(ge=1, le=52)] = 12,
) -> dict[str, Any]:
    """7-1 위험도 추이 (질환별 주마다 마지막 예측)."""
    return await service.risk_trend(user, weeks)


@dashboard_router.get("/logs")
async def get_log_graph(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[DashboardService, Depends(DashboardService)],
    log_type: str,
    start_on: Annotated[date, Query(alias="from")],
    end_on: Annotated[date, Query(alias="to")],
    bucket: Literal["raw", "day", "week"] = "raw",
) -> dict[str, Any]:
    """7-2 항목별 그래프 (집에서 잰 값만)."""
    return await service.logs(user, log_type, start_on, end_on, bucket)


@dashboard_router.get("/summary")
async def get_summary(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[DashboardService, Depends(DashboardService)],
    week_start: date | None = None,
) -> dict[str, Any]:
    """7-3 요약 카드 (week_start 생략 시 이번 주)."""
    return await service.summary(user, week_start)
