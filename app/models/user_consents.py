from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.users import User


class Agreement(StrEnum):
    TERMS = "TERMS"
    PRIVACY = "PRIVACY"
    SENSITIVE_HEALTH = "SENSITIVE_HEALTH"
    MODEL_IMPROVEMENT = "MODEL_IMPROVEMENT"  # 선택: 모델 개선에 내 데이터 활용 (REQ-NFR-018, docs/feedback-loop.md)


# 가입에 꼭 필요한 동의. 철회는 탈퇴로만 (api.md 2-1·2-6, 정할 것 22번)
REQUIRED_AGREEMENTS = frozenset({Agreement.TERMS, Agreement.PRIVACY, Agreement.SENSITIVE_HEALTH})


class UserConsent(models.Model):
    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="user_consents", on_delete=fields.CASCADE
    )
    # 탈퇴해도 users 행은 비활성으로 남김(api.md 2-8) → 동의 기록도 users를 따라감
    agreement = fields.CharEnumField(enum_type=Agreement)
    version = fields.CharField(max_length=20)  # 'v1.0'
    is_agreed = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)  # 동의한 순간 자동으로 찍히게

    class Meta:
        table = "user_consents"
