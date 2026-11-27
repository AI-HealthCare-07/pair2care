from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.recommendations import Recommendation
    from app.models.users import User


class FeedbackReason(StrEnum):
    NOT_FIT = "NOT_FIT"  # 나한테 안 맞아요
    ALREADY_DOING = "ALREADY_DOING"  # 이미 하고 있어요
    TOO_HARD = "TOO_HARD"  # 너무 어려워요
    WRONG_CONTENT = "WRONG_CONTENT"  # 내용이 이상해요
    OTHER = "OTHER"  # 기타


class RecommendationFeedback(models.Model):
    """추천에 대한 사용자 만족도 (api.md 11-9, REQ-NFR-019). 팀의 "적절함" 라벨과 다름."""

    id = fields.BigIntField(primary_key=True)
    # 추천당 1행, 다시 누르면 덮어씀
    recommendation: fields.OneToOneRelation["Recommendation"] = fields.OneToOneField(
        "models.Recommendation", related_name="feedback", on_delete=fields.CASCADE
    )
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="recommendation_feedbacks", on_delete=fields.CASCADE
    )
    is_helpful = fields.BooleanField()
    reason = fields.CharEnumField(enum_type=FeedbackReason, null=True)  # 별로예요일 때만, 안 고르면 null
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "recommendation_feedbacks"
