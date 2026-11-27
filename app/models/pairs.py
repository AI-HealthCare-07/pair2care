"""짝꿍 관계 모델 (docs/erd.dbml)."""

from enum import StrEnum

from tortoise import fields, models


class PairStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    ENDED = "ENDED"


class Pair(models.Model):
    id = fields.BigIntField(primary_key=True)

    requester = fields.ForeignKeyField(
        "models.User",
        related_name="pair_requests",
        on_delete=fields.CASCADE,
    )

    partner = fields.ForeignKeyField(
        "models.User",
        related_name="pair_invitations",
        on_delete=fields.SET_NULL,
        null=True,
    )

    invite_code = fields.CharField(
        max_length=128,
        unique=True,
    )

    pair_key = fields.CharField(
        max_length=50,
        unique=True,
        null=True,
    )

    status = fields.CharEnumField(
        enum_type=PairStatus,
        default=PairStatus.PENDING,
    )

    accepted_at = fields.DatetimeField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "pairs"
