from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.users import User


class CheckupSource(StrEnum):
    MANUAL = "MANUAL"  # 사용자 직접 입력
    OCR = "OCR"  # 검진 결과지 사진 인식 (12/4 이후)


class CheckupRecord(models.Model):
    """건강검진 결과지 한 장 = 한 행.

    수치는 모두 선택이지만 최소 1개는 있어야 함 (API에서 검사, api.md 4-1).
    대시보드 혈압 그래프에는 안 씀 (집에서 잰 혈압은 health_logs).
    대사증후군 판정은 저장하지 않고 이 수치로 매번 계산 (app/services/prediction/criteria.py).
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="checkup_records", on_delete=fields.CASCADE
    )
    checked_on = fields.DateField()  # 검진 받은 날
    systolic_bp = fields.SmallIntField(null=True)  # 수축기 혈압 mmHg
    diastolic_bp = fields.SmallIntField(null=True)  # 이완기 혈압 mmHg
    fasting_glucose = fields.SmallIntField(null=True)  # 공복혈당 mg/dL
    waist_cm = fields.DecimalField(max_digits=4, decimal_places=1, null=True)  # 허리둘레 cm (대사증후군은 이 값만 씀)
    triglyceride = fields.SmallIntField(null=True)  # 중성지방 mg/dL
    hdl_cholesterol = fields.SmallIntField(null=True)  # HDL 콜레스테롤 mg/dL
    hba1c = fields.DecimalField(max_digits=3, decimal_places=1, null=True)  # 당화혈색소 %, 선택
    source = fields.CharEnumField(enum_type=CheckupSource, default=CheckupSource.MANUAL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)  # 오타 수정·빈 항목 추가 입력 추적

    class Meta:
        table = "checkup_records"
        indexes = (("user_id", "checked_on"),)  # 내 가장 최근 검진 조회용 (예측 기준표·대사증후군)
