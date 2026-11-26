
"""8-7 챌린지 생성 요청 DTO (docs/api.md)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ChallengeCreateRequest(BaseModel):
    challenge_template_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)
    times_per_week: int = Field(ge=1, le=7)
    starts_on: date | None = None
    ends_on: date | None = None
    mode: Literal["SOLO", "PAIR", "GROUP"]
    invite_user_ids: list[int] = Field(default_factory=list)


class ChallengeCheckRequest(BaseModel):
    """8-10. 챌린지 완료 체크 요청."""

    checked_on: date | None = None

