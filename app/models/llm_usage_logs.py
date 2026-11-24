"""LLM 요청 1건당 사용량 기록. 프롬프트/건강정보는 저장 금지."""

from enum import StrEnum

from tortoise import fields, models


class LlmFeature(StrEnum):
    DAILY_ACTION = "DAILY_ACTION"
    MEAL_ALTERNATIVE = "MEAL_ALTERNATIVE"
    WEATHER_TIP = "WEATHER_TIP"
    RISK_EXPLANATION = "RISK_EXPLANATION"
    WEEKLY_REPORT = "WEEKLY_REPORT"
    MEAL_VISION = "MEAL_VISION"
    RAG_EMBEDDING = "RAG_EMBEDDING"


class LlmUsageLog(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="llm_usage_logs", null=True, on_delete=fields.SET_NULL)
    recommendation = fields.ForeignKeyField(
        "models.Recommendation", related_name="usage_logs", null=True, on_delete=fields.SET_NULL
    )
    meal_id = fields.BigIntField(null=True)
    feature = fields.CharEnumField(enum_type=LlmFeature)
    model = fields.CharField(max_length=50)
    input_tokens = fields.IntField(default=0)
    output_tokens = fields.IntField(default=0)
    cache_creation_tokens = fields.IntField(default=0)
    cache_read_tokens = fields.IntField(default=0)
    estimated_cost_usd = fields.DecimalField(max_digits=10, decimal_places=6, null=True)
    is_success = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "llm_usage_logs"
        indexes = (("feature", "created_at"), ("user_id", "created_at"))
