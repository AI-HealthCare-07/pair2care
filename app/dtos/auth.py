from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import validate_password
from app.dtos.users import UserInfoResponse
from app.models.user_consents import Agreement
from app.models.users import Gender


class ConsentItem(BaseModel):
    agreement: Agreement
    version: str
    is_agreed: bool


def _no_duplicate_agreement(consents: list[ConsentItem]) -> list[ConsentItem]:
    if len({c.agreement for c in consents}) != len(consents):
        raise ValueError("같은 동의 항목을 두 번 보낼 수 없어요.")
    return consents


class SignUpRequest(BaseModel):
    email: Annotated[EmailStr, Field(max_length=255)]
    password: Annotated[str, AfterValidator(validate_password)]
    nickname: Annotated[str, Field(min_length=2, max_length=20)]
    gender: Gender
    # 만 14세 미만은 서비스에서 400 SIGNUP_UNDER_14 (여기서 막으면 422라 어느 칸인지 code·field를 못 줌)
    birthday: Annotated[date, Field(description="Date Format: YYYY-MM-DD")]
    # 필수 3종 동의·버전은 서비스에서 확인해 400으로 응답, 선택 MODEL_IMPROVEMENT는 없어도 됨 (api.md 2-1)
    consents: Annotated[list[ConsentItem], AfterValidator(_no_duplicate_agreement)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]


class TokenRefreshResponse(BaseModel):
    access_token: str


class LoginResponse(TokenRefreshResponse):
    has_health_profile: bool  # 가입 설문(ONBOARDING)을 했는지 → false면 프론트가 S-06으로 보냄 (api.md 2-2)


class SignUpResponse(LoginResponse):
    user: UserInfoResponse  # 가입한 내 정보 (api.md 2-1). 설문 여부는 부모 LoginResponse의 has_health_profile
