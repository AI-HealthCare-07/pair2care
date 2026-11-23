from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import ConsentItem, LoginRequest, SignUpRequest
from app.models.user_consents import Agreement
from app.models.users import User
from app.repositories.user_consent_repository import UserConsentRepository
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.consent_repo = UserConsentRepository()
        self.jwt_service = JwtService()

    async def signup(self, data: SignUpRequest) -> User:
        # 이메일 중복 체크
        await self.check_email_exists(data.email)

        # 필수 약관 3종 동의·버전 확인 (api.md 2-1)
        self.check_required_consents(data.consents)

        # 회원 + 동의 기록을 한 트랜잭션으로 저장 (동의 없이 가입만 된 계정이 생기지 않게)
        async with in_transaction():
            user = await self.user_repo.create_user(
                email=data.email,
                hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
                nickname=data.nickname,
                gender=data.gender,
                birthday=data.birthday,
            )
            await self.consent_repo.create_many(user_id=user.id, consents=data.consents)

        return user

    async def authenticate(self, data: LoginRequest) -> User:
        # 이메일로 사용자 조회
        email = str(data.email)
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 비밀번호 검증
        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 활성 사용자 체크
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="비활성화된 계정입니다.")

        return user

    async def login(self, user: User) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(user.id)
        return self.jwt_service.issue_jwt_pair(user)

    async def check_email_exists(self, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.")

    @staticmethod
    def check_required_consents(consents: list[ConsentItem]) -> None:
        agreed = {c.agreement for c in consents if c.is_agreed and c.version == config.TERMS_VERSION}
        if agreed != set(Agreement):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="필수 약관에 모두 동의해 주세요.")
