from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi import Response as EmptyResponse
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
        max_age=config.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
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


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> EmptyResponse:
    # 로그인 없이 항상 204: access 토큰(30분)이 만료된 뒤에도 refresh 쿠키를 지울 수 있어야 함 (api.md 2-4)
    # access 토큰은 서버에서 막지 않음(블랙리스트 없음) → refresh 쿠키만 지움 (정할 것 23번)
    # shortcut: push_endpoint 구독 삭제는 push_subscriptions 모델이 생기면 추가.
    #           그때는 토큰이 있으면 그 사용자의 구독만 지움 (인증 없이 지우면 endpoint만 알면 남의 구독도 지워짐)
    resp = EmptyResponse(status_code=status.HTTP_204_NO_CONTENT)
    # 지우려면 set_refresh_cookie와 domain·secure가 같아야 브라우저가 같은 쿠키로 봄
    resp.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
    )
    return resp
