
"""챌린지 참여자 모델 (docs/erd.dbml)."""

from enum import StrEnum

from tortoise import fields, models


class ParticipantStatus(StrEnum):
    INVITED = "INVITED"
    JOINED = "JOINED"
    LEFT = "LEFT"


class ChallengeParticipant(models.Model):
    id = fields.BigIntField(primary_key=True)

    challenge = fields.ForeignKeyField(
        "models.Challenge",
        related_name="participants",
        on_delete=fields.CASCADE,
    )

    user = fields.ForeignKeyField(
        "models.User",
        related_name="challenge_participations",
        on_delete=fields.CASCADE,
    )

    status = fields.CharEnumField(
        enum_type=ParticipantStatus,
        default=ParticipantStatus.INVITED,
    )

    times_per_week = fields.IntField(null=True)
    joined_at = fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "challenge_participants"
        unique_together = (("challenge_id", "user_id"),)
