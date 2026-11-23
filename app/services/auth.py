from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from redis.asyncio import Redis
from starlette import status
from tortoise.exceptions import IntegrityError
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

LOGIN_FAIL_KEY_PREFIX = "login_fail:"
LOGIN_FAIL_LIMIT = 5
LOGIN_LOCK_SECONDS = 10 * 60
LOGIN_LOCKED_DETAIL = "로그인을 5번 틀려서 10분 뒤에 다시 시도할 수 있어요."


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
        # 같은 이메일로 동시에 가입하면 둘 다 위 중복 체크를 통과할 수 있음 → DB unique 위반을 409로
        try:
            async with in_transaction():
                user = await self.user_repo.create_user(
                    email=data.email,
                    hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
                    nickname=data.nickname,
                    gender=data.gender,
                    birthday=data.birthday,
                )
                await self.consent_repo.create_many(user_id=user.id, consents=data.consents)
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.") from None

        return user

    async def authenticate(self, data: LoginRequest) -> User:
        email = str(data.email)
        # 이메일별 실패 횟수 (api.md 2-2). 가입 안 된 이메일도 똑같이 세서 잠금으로 가입 여부를 알 수 없게
        fail_key = f"{LOGIN_FAIL_KEY_PREFIX}{email.lower()}"
        # 요청마다 새로 연결 (테스트·워커마다 이벤트 루프가 달라서 전역 커넥션 풀을 쓰지 않음)
        async with Redis(host=config.REDIS_HOST, port=config.REDIS_PORT) as redis:
            if int(await redis.get(fail_key) or 0) >= LOGIN_FAIL_LIMIT:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=LOGIN_LOCKED_DETAIL)

            user = await self.user_repo.get_user_by_email(email)
            # 이메일 없음·비밀번호 틀림·탈퇴 계정 모두 같은 401 (어느 쪽인지 알려 주면 가입 이메일이 드러남)
            if not user or not verify_password(data.password, user.hashed_password) or not user.is_active:
                fails = await redis.incr(fail_key)
                await redis.expire(fail_key, LOGIN_LOCK_SECONDS)
                if fails >= LOGIN_FAIL_LIMIT:
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=LOGIN_LOCKED_DETAIL)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 맞지 않아요."
                )

            await redis.delete(fail_key)  # 성공하면 횟수 초기화
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
