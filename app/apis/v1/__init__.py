from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.health_profile_routers import health_profile_router
from app.apis.v1.recommendation_routers import recommendation_router
from app.apis.v1.risk_prediction_routers import risk_prediction_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(recommendation_router)
v1_routers.include_router(health_profile_router)
v1_routers.include_router(risk_prediction_router)
