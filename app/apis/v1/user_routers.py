from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.auth import ConsentItem
from app.dtos.consents import ConsentListResponse, ConsentStatus
from app.dtos.users import UserInfoResponse, UserUpdateRequest
from app.models.users import User
from app.services.consents import ConsentService
from app.services.users import UserManageService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def user_me_info(
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    return Response(await user_manage_service.get_me(user), status_code=status.HTTP_200_OK)


@user_router.patch("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def update_user_me_info(
    update_data: UserUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    updated_user = await user_manage_service.update_user(user=user, data=update_data)
    return Response(await user_manage_service.get_me(updated_user), status_code=status.HTTP_200_OK)


@user_router.get("/me/consents", response_model=ConsentListResponse, status_code=status.HTTP_200_OK)
async def get_my_consents(
    user: Annotated[User, Depends(get_request_user)],
    consent_service: Annotated[ConsentService, Depends(ConsentService)],
) -> ConsentListResponse:
    return await consent_service.get_consents(user.id)


@user_router.post("/me/consents", response_model=ConsentStatus, status_code=status.HTTP_201_CREATED)
async def save_my_consent(
    consent: ConsentItem,
    user: Annotated[User, Depends(get_request_user)],
    consent_service: Annotated[ConsentService, Depends(ConsentService)],
) -> ConsentStatus:
    return await consent_service.save_consent(user.id, consent)
