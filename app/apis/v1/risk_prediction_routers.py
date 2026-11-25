"""5장 위험 예측 API (조회·시뮬레이션·다시 계산)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.dependencies.security import get_request_user
from app.models.users import User
from app.services.prediction.service import PredictionQueryService, PredictionService
from app.services.prediction.simulation import SimulationRequest

risk_prediction_router = APIRouter(prefix="/risk-predictions", tags=["risk-predictions"])


@risk_prediction_router.get("/latest")
async def get_latest_predictions(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[PredictionQueryService, Depends(PredictionQueryService)],
) -> dict[str, Any]:
    """5-2 최근 예측 (S-09·S-12). 설문이 없으면 404."""
    return await service.get_latest(user)


@risk_prediction_router.post("/simulate")
async def simulate_habits(
    data: SimulationRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[PredictionQueryService, Depends(PredictionQueryService)],
) -> dict[str, Any]:
    """5-4 습관 시뮬레이션 (S-10). 저장하지 않음."""
    return await service.simulate(user, data.changes)


@risk_prediction_router.post("/retry")
async def retry_predictions(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[PredictionService, Depends(PredictionService)],
) -> dict[str, Any]:
    """5-5 다시 계산 (S-09 C-02). 이미 예측이 있으면 409, 또 실패하면 503."""
    return await service.retry_latest(user)


@risk_prediction_router.get("/{prediction_id}")
async def get_prediction_detail(
    prediction_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[PredictionQueryService, Depends(PredictionQueryService)],
) -> dict[str, Any]:
    """5-3 예측 상세. 남의 것이면 404."""
    return await service.get_detail(user, prediction_id)
