"""기본 챌린지 템플릿 모델 (docs/erd.dbml)."""

from enum import StrEnum

from tortoise import fields, models


class ChallengeCategory(StrEnum):
    WALK = "WALK"
    WATER = "WATER"
    EXERCISE = "EXERCISE"
    STRETCH = "STRETCH"
    LESS_ALCOHOL = "LESS_ALCOHOL"
    WEIGHT = "WEIGHT"
    NO_SMOKING = "NO_SMOKING"


class ChallengeTemplate(models.Model):
    id = fields.BigIntField(primary_key=True)
    title = fields.CharField(max_length=100)
    category = fields.CharEnumField(
        enum_type=ChallengeCategory,
        max_length=30,
    )
    default_times_per_week = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "challenge_templates"
