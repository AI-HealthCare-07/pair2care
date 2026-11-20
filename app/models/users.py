from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=128)
    nickname = fields.CharField(max_length=50)
    gender = fields.CharEnumField(enum_type=Gender)
    birthday = fields.DateField()
    quiet_start = fields.TimeField(null=True)  # 방해 금지 시작, 안 쓰면 비어 있음
    quiet_end = fields.TimeField(null=True)  # 방해 금지 끝
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
