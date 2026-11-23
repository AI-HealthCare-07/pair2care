from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.users import Gender


class UserUpdateRequest(BaseModel):
    nickname: Annotated[str | None, Field(None, min_length=2, max_length=20)]
    # 성별·생년월일은 예측 입력이라 직접 수정 불가 → 보내면 서비스에서 400 (api.md 2-5)
    gender: Annotated[Gender | None, Field(None, description="수정 불가, 보내면 400")]
    birthday: Annotated[date | None, Field(None, description="수정 불가, 보내면 400")]


class UserInfoResponse(BaseSerializerModel):
    id: int
    nickname: str
    email: str
    birthday: date
    gender: Gender
    created_at: datetime
