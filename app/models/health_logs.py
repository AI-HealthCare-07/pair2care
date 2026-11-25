from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.users import User


class HealthLogType(StrEnum):
    """기록 종류 (ERD health_log_type, api.md 6-0)."""

    # 일일 기록 (6-1)
    BLOOD_PRESSURE = "BLOOD_PRESSURE"  # 수축기 / 이완기 mmHg, 하루 여러 번
    BLOOD_GLUCOSE = "BLOOD_GLUCOSE"  # mg/dL
    ALCOHOL = "ALCOHOL"  # 마신 잔 수
    EXERCISE = "EXERCISE"  # 운동 시간(분)
    STEPS = "STEPS"  # 걸음 수, 하루 1행 덮어씀
    CONDITION = "CONDITION"  # 좋음 2 · 보통 1 · 나쁨 0, 하루 1행 덮어씀
    WEIGHT = "WEIGHT"  # kg
    # 주간 기록 (6-4, 주 1행, measured_at = 그 주 월요일 00:00 KST)
    WALK_DAYS = "WALK_DAYS"
    STRENGTH_DAYS = "STRENGTH_DAYS"
    SITTING_HOURS = "SITTING_HOURS"
    SLEEP = "SLEEP"  # 주중 / 주말 시간
    BREAKFAST = "BREAKFAST"
    STRESS = "STRESS"


class HealthLog(models.Model):
    """집에서 잰 혈압·혈당, 음주, 운동, 컨디션, 주간 기록 6종 (REQ-DASH-001~002·005).

    혈압처럼 하루 여러 번 재는 기록이 있어서 유니크 제약은 없음. 하루·한 주 1행 규칙은 API에서 지킴.
    주간 기록 값은 예측에 안 써서 국건영 코드가 아닌 우리 코드.
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="health_logs", on_delete=fields.CASCADE
    )
    log_type = fields.CharEnumField(enum_type=HealthLogType, max_length=20)
    value = fields.DecimalField(max_digits=10, decimal_places=2)
    value2 = fields.DecimalField(max_digits=10, decimal_places=2, null=True)  # 이완기 혈압, 주말 수면
    unit = fields.CharField(max_length=20, null=True)  # 서버가 종류에 맞게 채움 (클라이언트 값은 무시)
    measured_at = fields.DatetimeField()
    memo = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)  # 수정 허용 (api.md 정할 것 4번, 11/23)

    user_id: int

    class Meta:
        table = "health_logs"
        indexes = (("user_id", "log_type", "measured_at"),)  # 종류별 기간 조회 (그래프)
