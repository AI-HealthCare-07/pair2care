from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.challenge_routers import challenge_router
from app.apis.v1.challenge_template_routers import challenge_template_router
from app.apis.v1.checkup_record_routers import checkup_record_router
from app.apis.v1.dashboard_routers import dashboard_router
from app.apis.v1.health_log_routers import health_log_router
from app.apis.v1.health_profile_routers import health_profile_router
from app.apis.v1.recommendation_routers import recommendation_router
from app.apis.v1.risk_prediction_routers import risk_prediction_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(challenge_template_router)
v1_routers.include_router(challenge_router)
v1_routers.include_router(recommendation_router)
v1_routers.include_router(health_profile_router)
v1_routers.include_router(health_log_router)
v1_routers.include_router(dashboard_router)
v1_routers.include_router(risk_prediction_router)
v1_routers.include_router(checkup_record_router)
