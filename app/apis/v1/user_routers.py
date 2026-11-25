from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.users import UserInfoResponse, UserUpdateRequest
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.users import UserManageService

user_router = APIRouter(prefix="/users", tags=["users"])


async def to_user_info(user: User) -> dict[str, Any]:
    """/users/me 응답 (GET·PATCH 같이 씀). has_health_profile은 User 컬럼이 아니라 따로 채움 (api.md 2-5)."""
    has_profile = await UserRepository().has_onboarding_profile(user.id)
    body = UserInfoResponse.model_validate(user).model_copy(update={"has_health_profile": has_profile})
    return body.model_dump()


@user_router.get("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def user_me_info(
    user: Annotated[User, Depends(get_request_user)],
) -> Response:
    return Response(await to_user_info(user), status_code=status.HTTP_200_OK)


@user_router.patch("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def update_user_me_info(
    update_data: UserUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    updated_user = await user_manage_service.update_user(user=user, data=update_data)
    return Response(await to_user_info(updated_user), status_code=status.HTTP_200_OK)
