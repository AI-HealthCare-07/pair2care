from enum import StrEnum

from tortoise import fields, models


class Agreement(StrEnum):
    TERMS = "TERMS"
    PRIVACY = "PRIVACY"
    SENSITIVE_HEALTH = "SENSITIVE_HEALTH"


class UserConsent(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="user_consents", on_delete=fields.CASCADE)
    # 탈퇴해도 users 행은 비활성으로 남김(api.md 2-8) → 동의 기록도 users를 따라감
    agreement = fields.CharEnumField(enum_type=Agreement)
    version = fields.CharField(max_length=20)  # 'v1.0'
    is_agreed = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)  # 동의한 순간 자동으로 찍히게

    class Meta:
        table = "user_consents"
