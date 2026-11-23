from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse as Response

from app.core import config
from app.core.config import Env
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.dtos.auth import LoginRequest, LoginResponse, SignUpRequest, SignUpResponse, TokenRefreshResponse
from app.dtos.users import UserInfoResponse
from app.services.auth import AuthService
from app.services.jwt import JwtService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def set_refresh_cookie(resp: Response, tokens: dict[str, AccessToken | RefreshToken]) -> None:
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )


@auth_router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignUpRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.signup(request)
    # 가입하면 바로 로그인 상태로 응답 → S-06 설문으로 이어짐 (api.md 2-1)
    tokens = await auth_service.login(user)
    content = SignUpResponse(
        access_token=str(tokens["access_token"]),
        user=UserInfoResponse.model_validate(user),
        has_health_profile=False,  # 막 가입했으니 설문 전
    ).model_dump(mode="json")
    resp = Response(content=content, status_code=status.HTTP_201_CREATED)
    set_refresh_cookie(resp, tokens)
    return resp


@auth_router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.authenticate(request)
    tokens = await auth_service.login(user)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
    )
    set_refresh_cookie(resp, tokens)
    return resp


@auth_router.get("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    access_token = jwt_service.refresh_jwt(refresh_token)
    return Response(
        content=TokenRefreshResponse(access_token=str(access_token)).model_dump(), status_code=status.HTTP_200_OK
    )
