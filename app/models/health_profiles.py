from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.users import User


class SurveyKind(StrEnum):
    ONBOARDING = "ONBOARDING"  # 가입 때 첫 설문
    WEEKLY = "WEEKLY"  # 주 1회 재설문
    EDIT = "EDIT"  # 마이(S-27)에서 고치기: 21문항 전부, 새 행으로 (정할 것 1번, 11/26). 재설문 주기에는 안 셈


class HealthProfile(models.Model):
    """설문 한 번 = 한 행 (재설문도 새 행으로 쌓음, 수정 없음).

    코드 값은 docs/survey-mapping.md (국건영 코드 그대로, 건너뛴 문항도 8·888 코드로 저장).
    ERD의 tinyint 컬럼은 Tortoise에 1바이트 정수 필드가 없어 SmallIntField로 둠 (값 범위 1~9·888은 그대로).
    재설문에서 안 묻는 항목은 직전 행 값 복사 → 최신 행 하나가 항상 완전한 모델 입력 (허리둘레는 복사 안 함).
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="health_profiles", on_delete=fields.CASCADE
    )
    kind = fields.CharEnumField(enum_type=SurveyKind)
    survey_version = fields.CharField(max_length=20)  # 'v1.0', 질문이 바뀌면 올림

    # 신체
    height_cm = fields.DecimalField(max_digits=4, decimal_places=1)  # HE_ht, 예측
    weight_kg = fields.DecimalField(max_digits=4, decimal_places=1)  # HE_wt, 예측
    waist_cm = fields.DecimalField(max_digits=4, decimal_places=1, null=True)  # HE_wc, 기록용 (선택)

    # 가족력: 예 1 / 아니오 0 / 모름 9 / 형제자매 없음 8 (형제자매만)
    father_diabetes_history = fields.SmallIntField()  # HE_DMfh1
    mother_diabetes_history = fields.SmallIntField()  # HE_DMfh2
    sibling_diabetes_history = fields.SmallIntField()  # HE_DMfh3
    father_hypertension_history = fields.SmallIntField()  # HE_HPfh1
    mother_hypertension_history = fields.SmallIntField()  # HE_HPfh2
    sibling_hypertension_history = fields.SmallIntField()  # HE_HPfh3

    # 음주
    alcohol_ever = fields.SmallIntField()  # BD1: 없다 1 / 있다 2 (건너뛰기용)
    alcohol_frequency = fields.SmallIntField()  # BD1_11: 1~6, 비해당 8
    alcohol_amount = fields.SmallIntField()  # BD2_1: 1~5, 비해당 8
    binge_frequency = fields.SmallIntField()  # BD2_31: 1~5, 비해당 8, 기록용

    # 흡연
    smoking_lifetime = fields.SmallIntField()  # BS1_1: 5갑 미만 1 / 이상 2 / 없음 3 (건너뛰기용)
    smoking_current = fields.SmallIntField()  # BS3_1: 매일 1 / 가끔 2 / 지금은 안 피움 3, 비해당 8
    cigarettes_per_day = fields.SmallIntField()  # BS3_2: 1~60, 비해당 888, 기록용
    heated_tobacco = fields.SmallIntField()  # BS12_47: 매일 1 / 가끔 2 / 과거 3 / 안 함 8, 기록용
    liquid_ecig = fields.SmallIntField()  # BS12_2: 현재 1 / 과거 2 / 안 함 8, 기록용

    # 진단 여부 ("예"면 그 질환은 예측 안 함)
    is_hypertension_diagnosed = fields.BooleanField()
    is_diabetes_diagnosed = fields.BooleanField()
    is_pregnant = fields.BooleanField(null=True)  # 여성만, 남성은 null. "예"면 두 질환 모두 예측 안 함

    created_at = fields.DatetimeField(auto_now_add=True)  # 설문 응답 시각 (예측 나이 기준)

    class Meta:
        table = "health_profiles"
        indexes = (("user_id", "created_at"),)  # 내 최신 설문 조회용
