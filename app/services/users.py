from typing import Any

from fastapi import HTTPException
from starlette import status
from tortoise.transactions import in_transaction

from app.dtos.users import UserUpdateRequest
from app.models.users import User
from app.repositories.user_repository import UserRepository


class UserManageService:
    def __init__(self):
        self.repo = UserRepository()

    async def update_user(self, user: User, data: UserUpdateRequest) -> User:
        # 성별·생년월일은 예측 입력이라 직접 수정 불가 (api.md 2-5, 정할 것 24번)
        if data.gender is not None or data.birthday is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="성별·생년월일은 바꿀 수 없어요. 고치려면 관리자에게 요청해 주세요.",
            )
        async with in_transaction():
            await self.repo.update_instance(user=user, data=self._changes(data))
            await user.refresh_from_db()
        return user

    @staticmethod
    def _changes(data: UserUpdateRequest) -> dict[str, Any]:
        # 보낸 필드만 반영. region은 null도 "선택 해제"라 그대로 넘기고, nickname null은 무시(바꾸지 않음)
        changes = data.model_dump(exclude_unset=True, include={"nickname", "region"})
        if changes.get("nickname") is None:
            changes.pop("nickname", None)
        return changes
