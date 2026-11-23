"""추천 상태 저장. ERD recommendations 규칙(api.md 11장)."""

from enum import StrEnum

from tortoise import fields, models


class RecommendationType(StrEnum):
    DAILY_ACTION = "DAILY_ACTION"
    MEAL_ALTERNATIVE = "MEAL_ALTERNATIVE"
    WEATHER_TIP = "WEATHER_TIP"
    RISK_EXPLANATION = "RISK_EXPLANATION"
    WEEKLY_REPORT = "WEEKLY_REPORT"


class GenerationStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Recommendation(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="recommendations", on_delete=fields.CASCADE)
    rec_type = fields.CharEnumField(enum_type=RecommendationType)
    target_on = fields.DateField()
    status = fields.CharEnumField(enum_type=GenerationStatus, default=GenerationStatus.PENDING)
    task_id = fields.UUIDField(null=True)
    content = fields.TextField(null=True)
    sources = fields.JSONField(null=True)
    # 현재 develop에는 risk_predictions·meals ORM 모델이 없으므로 ID를 저장한다.
    # 두 모델이 병합되면 FK 관계와 마이그레이션을 맞춰야 한다.
    risk_prediction_id = fields.BigIntField(null=True, unique=True)
    meal_id = fields.BigIntField(null=True, unique=True)
    model = fields.CharField(max_length=50, null=True)
    prompt_version = fields.CharField(max_length=30, null=True)
    retry_count = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "recommendations"
        indexes = (("user_id", "rec_type", "target_on"),)
