
"""사용자 챌린지 모델 (docs/erd.dbml)."""

from enum import StrEnum

from tortoise import fields, models


class ChallengeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ENDED = "ENDED"


class Challenge(models.Model):
    id = fields.BigIntField(primary_key=True)

    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="created_challenges",
        on_delete=fields.CASCADE,
    )

    challenge_template = fields.ForeignKeyField(
        "models.ChallengeTemplate",
        related_name="challenges",
        on_delete=fields.SET_NULL,
        null=True,
    )

    pair = fields.ForeignKeyField(
        "models.Pair",
        related_name="challenges",
        on_delete=fields.SET_NULL,
        null=True,
    )

    title = fields.CharField(max_length=100)
    times_per_week = fields.IntField()
    starts_on = fields.DateField()
    ends_on = fields.DateField(null=True)

    status = fields.CharEnumField(
        enum_type=ChallengeStatus,
        default=ChallengeStatus.ACTIVE,
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "challenges"
