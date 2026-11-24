"""11장 LLM 추천 API: 저장본 우선, POST만 비동기 큐 등록."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.models.users import User
from app.services.challenge_recommendations import ChallengeRecommendation, recommend_challenge
from app.services.recommendations import RecommendationService

recommendation_router = APIRouter(tags=["recommendations"])


@recommendation_router.get("/recommendations/daily")
async def get_daily(
    user: Annotated[User, Depends(get_request_user)],
    target_on: Annotated[date | None, Query()] = None,
) -> dict:
    return await RecommendationService().get_daily(user.id, target_on)


@recommendation_router.post("/recommendations/daily")
async def post_daily(user: Annotated[User, Depends(get_request_user)]) -> ORJSONResponse:
    code, data = await RecommendationService().post_daily(user.id)
    return ORJSONResponse(data, status_code=code)


@recommendation_router.get("/meals/{id}/recommendation")
async def get_meal_recommendation(id: int, user: Annotated[User, Depends(get_request_user)]) -> dict:
    return await RecommendationService().get_meal(user.id, id)


@recommendation_router.post("/meals/{id}/recommendation")
async def post_meal_recommendation(id: int, user: Annotated[User, Depends(get_request_user)]) -> ORJSONResponse:
    code, data = await RecommendationService().post_meal(user.id, id)
    return ORJSONResponse(data, status_code=code)


@recommendation_router.get("/recommendations/challenges/next")
async def get_next_challenge(
    user: Annotated[User, Depends(get_request_user)], response: Response
) -> ChallengeRecommendation | None:
    response.headers["Cache-Control"] = "no-store"
    return await recommend_challenge(user.id)
