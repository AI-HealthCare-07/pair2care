from enum import StrEnum
from typing import TYPE_CHECKING, Any

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.checkup_records import CheckupRecord
    from app.models.health_profiles import HealthProfile
    from app.models.users import User


class Disease(StrEnum):
    HYPERTENSION = "HYPERTENSION"
    DIABETES = "DIABETES"


class PredictionMethod(StrEnum):
    MODEL = "MODEL"  # 설문 모델 점수. 검진 수치가 있어도 항상 저장
    CHECKUP_CRITERIA = "CHECKUP_CRITERIA"  # 검진 수치 기준표 판정. score·model_version 없음


class RiskLevel(StrEnum):
    LOW = "LOW"  # 저위험 / 정상 (화면은 "상대적으로 낮음")
    CAUTION = "CAUTION"
    HIGH = "HIGH"


class RiskPrediction(models.Model):
    """예측 한 번 = 질환별 한 행 (기록용, 수정 없음). api.md 5-0·5-1.

    - 진단 "예"인 질환은 행을 만들지 않음. 대사증후군도 행 없음 (검진 수치로 매번 계산)
    - 검진 수치가 있으면 한 질환에 MODEL 행 + CHECKUP_CRITERIA 행 2개. 위험도 추이는 MODEL 행만
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="risk_predictions", on_delete=fields.CASCADE
    )
    health_profile: fields.ForeignKeyRelation["HealthProfile"] = fields.ForeignKeyField(
        "models.HealthProfile", related_name="risk_predictions", on_delete=fields.CASCADE
    )
    # 검진 기록을 지우면 null (이력은 input_snapshot에 남음)
    checkup_record: fields.ForeignKeyNullableRelation["CheckupRecord"] = fields.ForeignKeyField(
        "models.CheckupRecord", related_name="risk_predictions", null=True, on_delete=fields.SET_NULL
    )
    # 외래키 id 컬럼 (Tortoise가 만들어 줌, 타입 검사용 선언)
    user_id: int
    health_profile_id: int
    checkup_record_id: int | None

    disease = fields.CharEnumField(enum_type=Disease)
    method = fields.CharEnumField(enum_type=PredictionMethod, default=PredictionMethod.MODEL)
    score = fields.SmallIntField(null=True)  # 모델 확률 ×100 반올림 0~100. CHECKUP_CRITERIA는 null
    level = fields.CharEnumField(enum_type=RiskLevel)
    factors: fields.JSONField[list[dict[str, str]] | None] = fields.JSONField(
        null=True
    )  # 상위 3개 [{"feature": "bmi", "direction": "UP"}]
    model_version = fields.CharField(max_length=50, null=True)  # 'diabetes_risk:v1'. CHECKUP_CRITERIA는 null
    input_snapshot: fields.JSONField[dict[str, Any]] = (
        fields.JSONField()
    )  # MODEL: inputs + model_inputs / CHECKUP_CRITERIA: 검진 수치 + checked_on
    created_at = fields.DatetimeField(auto_now_add=True)  # 예측 시각

    class Meta:
        table = "risk_predictions"
        indexes = (("user_id", "disease", "created_at"),)  # 질환별 최신·추이 조회
