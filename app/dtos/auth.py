from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import validate_birthday, validate_password
from app.dtos.users import UserInfoResponse
from app.models.user_consents import Agreement
from app.models.users import Gender


class ConsentItem(BaseModel):
    agreement: Agreement
    version: str
    is_agreed: bool


class SignUpRequest(BaseModel):
    email: Annotated[EmailStr, Field(max_length=255)]
    password: Annotated[str, AfterValidator(validate_password)]
    nickname: Annotated[str, Field(min_length=2, max_length=20)]
    gender: Gender
    birthday: Annotated[date, Field(description="Date Format: YYYY-MM-DD"), AfterValidator(validate_birthday)]
    # 3종 모두 동의했는지·버전이 맞는지는 서비스에서 확인해 400으로 응답 (api.md 2-1)
    consents: list[ConsentItem]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]


class LoginResponse(BaseModel):
    access_token: str


class TokenRefreshResponse(LoginResponse): ...


class SignUpResponse(LoginResponse):
    user: UserInfoResponse
    has_health_profile: bool  # 가입 설문(ONBOARDING)을 했는지 → 프론트가 S-06으로 보낼지 정함
