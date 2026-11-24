from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.users import Gender, Region


class UserUpdateRequest(BaseModel):
    nickname: Annotated[str | None, Field(None, min_length=2, max_length=20)]
    # 성별·생년월일은 예측 입력이라 직접 수정 불가 → 보내면 서비스에서 400 (api.md 2-5)
    gender: Annotated[Gender | None, Field(None, description="수정 불가, 보내면 400")]
    birthday: Annotated[date | None, Field(None, description="수정 불가, 보내면 400")]
    # null을 보내면 선택 해제(날씨 안 씀). 17개 밖의 값은 422 (api.md 2-5·11-7)
    region: Annotated[Region | None, Field(None, description="시·도, null이면 선택 해제")]


class UserInfoResponse(BaseSerializerModel):
    id: int
    nickname: str
    email: str
    birthday: date
    gender: Gender
    region: Region | None
    created_at: datetime
