from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.recommendations import GenerationStatus, RecommendationType


class RecommendationQueued(BaseModel):
    recommendation_id: int
    task_id: str
    status: GenerationStatus = GenerationStatus.PENDING


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rec_type: RecommendationType
    target_on: date
    meal_id: int | None
    status: GenerationStatus
    content: str | None
    sources: list[dict[str, Any]] | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
