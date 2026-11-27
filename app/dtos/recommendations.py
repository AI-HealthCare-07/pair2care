from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.recommendation_feedbacks import FeedbackReason
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
    my_feedback: "MyFeedback | None" = None  # 11-9에 남긴 피드백, 서비스가 채움
    created_at: datetime
    updated_at: datetime


class MyFeedback(BaseModel):
    is_helpful: bool
    reason: FeedbackReason | None


class FeedbackRequest(BaseModel):
    is_helpful: bool
    reason: FeedbackReason | None = None

    @model_validator(mode="after")
    def reason_only_when_not_helpful(self) -> "FeedbackRequest":
        # 도움 돼요에 이유를 보내면 422 (api.md 11-9)
        if self.is_helpful and self.reason is not None:
            raise ValueError("도움 돼요에는 이유를 보내지 않아요.")
        return self


class FeedbackResponse(BaseModel):
    recommendation_id: int
    is_helpful: bool
    reason: FeedbackReason | None
    updated_at: datetime


RecommendationRead.model_rebuild()
