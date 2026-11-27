"""챌린지 완료 체크 기록 모델 (docs/erd.dbml)."""

from tortoise import fields, models


class ChallengeCheck(models.Model):
    id = fields.BigIntField(primary_key=True)

    challenge = fields.ForeignKeyField(
        "models.Challenge",
        related_name="checks",
        on_delete=fields.CASCADE,
    )

    user = fields.ForeignKeyField(
        "models.User",
        related_name="challenge_checks",
        on_delete=fields.CASCADE,
    )

    checked_on = fields.DateField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "challenge_checks"
        unique_together = (("challenge_id", "user_id", "checked_on"),)
