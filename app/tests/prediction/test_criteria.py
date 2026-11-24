from datetime import date
from decimal import Decimal

import pytest

from app.models.users import Gender
from app.services.prediction.criteria import (
    CRITERIA_VERSION,
    CheckupValues,
    Disease,
    MetabolicSyndromeResult,
    MetabolicSyndromeStatus,
    RiskLevel,
    is_checkup_valid,
    judge_checkup,
    judge_disease,
    judge_metabolic_syndrome,
)

CHECKED_ON = date(2026, 5, 10)
REFERENCE_ON = date(2026, 11, 23)


def checkup(**values: object) -> CheckupValues:
    return CheckupValues(checked_on=CHECKED_ON, **values)  # type: ignore[arg-type]


# ── 고혈압 기준표 (api.md 5-1) ──
@pytest.mark.parametrize(
    ("systolic_bp", "diastolic_bp", "expected"),
    [
        (129, 79, RiskLevel.LOW),  # 둘 다 정상
        (130, 70, RiskLevel.CAUTION),  # 수축기 130 이상 (경계 포함)
        (120, 80, RiskLevel.CAUTION),  # 이완기 80 이상 (경계 포함)
        (139, 89, RiskLevel.CAUTION),
        (140, 70, RiskLevel.HIGH),  # 수축기 140 이상
        (120, 90, RiskLevel.HIGH),  # 이완기 90 이상
        (150, 85, RiskLevel.HIGH),  # 둘 중 높은 단계
    ],
)
def test_hypertension_levels(systolic_bp: int, diastolic_bp: int, expected: RiskLevel) -> None:
    assert judge_disease(Disease.HYPERTENSION, checkup(systolic_bp=systolic_bp, diastolic_bp=diastolic_bp)) == expected


def test_hypertension_partial_values() -> None:
    # 있는 값이 기준 이상이면 그 값으로 판정
    assert judge_disease(Disease.HYPERTENSION, checkup(systolic_bp=135)) == RiskLevel.CAUTION
    assert judge_disease(Disease.HYPERTENSION, checkup(diastolic_bp=95)) == RiskLevel.HIGH
    # 있는 값이 정상이어도 하나가 빠졌으면 "정상"을 내지 않음
    assert judge_disease(Disease.HYPERTENSION, checkup(systolic_bp=120)) is None
    # 값이 하나도 없으면 판정 없음
    assert judge_disease(Disease.HYPERTENSION, checkup()) is None


# ── 당뇨 기준표 ──
@pytest.mark.parametrize(
    ("fasting_glucose", "hba1c", "expected"),
    [
        (99, Decimal("5.6"), RiskLevel.LOW),
        (100, Decimal("5.0"), RiskLevel.CAUTION),  # 공복혈당 100 이상 (경계 포함)
        (90, Decimal("5.7"), RiskLevel.CAUTION),  # 당화혈색소 5.7 이상 (경계 포함)
        (125, Decimal("6.4"), RiskLevel.CAUTION),
        (126, Decimal("5.0"), RiskLevel.HIGH),  # 공복혈당 126 이상
        (90, Decimal("6.5"), RiskLevel.HIGH),  # 당화혈색소 6.5 이상
    ],
)
def test_diabetes_levels(fasting_glucose: int, hba1c: Decimal, expected: RiskLevel) -> None:
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=fasting_glucose, hba1c=hba1c)) == expected


def test_diabetes_without_hba1c() -> None:
    # 일반 국가검진엔 당화혈색소가 없는 경우가 많음 → 공복혈당이 정상이면 판정하지 않음
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=95)) is None
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=110)) == RiskLevel.CAUTION


def test_float_and_decimal_give_same_result() -> None:
    # float 5.7과 Decimal("5.7")을 그대로 비교하면 경계에서 결과가 갈림 → 같은 결과여야 함
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=90, hba1c=5.7)) == RiskLevel.CAUTION
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=90, hba1c=Decimal("5.7"))) == RiskLevel.CAUTION
    assert judge_disease(Disease.DIABETES, checkup(fasting_glucose=90, hba1c=6.5)) == RiskLevel.HIGH


# ── 유효기간 1년 ──
def test_checkup_valid_period() -> None:
    assert is_checkup_valid(date(2025, 11, 23), REFERENCE_ON)  # 딱 1년 전은 유효
    assert not is_checkup_valid(date(2025, 11, 22), REFERENCE_ON)  # 1년 하루 전은 만료
    assert is_checkup_valid(date(2026, 11, 30), REFERENCE_ON)  # 설문 뒤에 넣은 검진도 유효
    # 윤년: 2/29 기준 1년 전은 2/28
    assert is_checkup_valid(date(2023, 2, 28), date(2024, 2, 29))
    assert not is_checkup_valid(date(2023, 2, 27), date(2024, 2, 29))


# ── 검진 1건 → 기준표 행 목록 ──
def test_judge_checkup_makes_rows_only_for_judgeable_diseases() -> None:
    # 혈압은 판정 가능, 당뇨는 공복혈당만 정상이라 판정 없음
    result = judge_checkup(checkup(systolic_bp=134, diastolic_bp=86, fasting_glucose=95), REFERENCE_ON)

    assert [j.disease for j in result] == [Disease.HYPERTENSION]
    assert result[0].level == RiskLevel.CAUTION
    assert result[0].input_snapshot == {
        "checked_on": "2026-05-10",
        "criteria_version": CRITERIA_VERSION,
        "systolic_bp": 134,
        "diastolic_bp": 86,
    }


def test_judge_checkup_both_diseases_and_decimal_snapshot() -> None:
    result = judge_checkup(
        checkup(systolic_bp=120, diastolic_bp=75, fasting_glucose=130, hba1c=Decimal("6.1")), REFERENCE_ON
    )

    levels = {j.disease: j.level for j in result}
    assert levels == {Disease.HYPERTENSION: RiskLevel.LOW, Disease.DIABETES: RiskLevel.HIGH}
    diabetes = next(j for j in result if j.disease == Disease.DIABETES)
    assert diabetes.input_snapshot["hba1c"] == 6.1  # JSON에 넣을 수 있게 float


def test_judge_checkup_none_or_expired() -> None:
    assert judge_checkup(None, REFERENCE_ON) == []
    expired = CheckupValues(checked_on=date(2024, 1, 1), systolic_bp=150, diastolic_bp=95)
    assert judge_checkup(expired, REFERENCE_ON) == []


# ── 대사증후군 ──
FULL_NORMAL = {
    "systolic_bp": 120,
    "diastolic_bp": 75,
    "fasting_glucose": 90,
    "waist_cm": Decimal("80.0"),
    "triglyceride": 100,
    "hdl_cholesterol": 60,
}


def metabolic(
    gender: Gender = Gender.MALE, *, htn: bool = False, dm: bool = False, **values: object
) -> MetabolicSyndromeResult:
    # 모두 정상인 검진에서 넘긴 값만 바꿔 판정 (None을 넘기면 그 값이 빠진 검진)
    return judge_metabolic_syndrome(
        checkup(**{**FULL_NORMAL, **values}),
        gender,
        is_hypertension_diagnosed=htn,
        is_diabetes_diagnosed=dm,
    )


def test_metabolic_all_normal_is_not_met() -> None:
    result = metabolic()
    assert result.status == MetabolicSyndromeStatus.NOT_MET
    assert result.met_count == 0


def test_metabolic_three_criteria_is_met() -> None:
    # 허리둘레·중성지방·HDL 3개 해당
    result = metabolic(waist_cm=Decimal("92.0"), triglyceride=150, hdl_cholesterol=39)
    assert result.status == MetabolicSyndromeStatus.MET
    assert result.met_count == 3


def test_metabolic_gender_thresholds() -> None:
    # 허리둘레 87, HDL 45: 남성은 둘 다 정상, 여성은 둘 다 해당
    male = metabolic(Gender.MALE, waist_cm=87, hdl_cholesterol=45, triglyceride=160)
    female = metabolic(Gender.FEMALE, waist_cm=87, hdl_cholesterol=45, triglyceride=160)
    assert male.criteria["waist"] is False and male.criteria["hdl_cholesterol"] is False
    assert female.criteria["waist"] is True and female.criteria["hdl_cholesterol"] is True
    assert male.status == MetabolicSyndromeStatus.NOT_MET
    assert female.status == MetabolicSyndromeStatus.MET


def test_metabolic_blood_pressure_uses_85_not_80() -> None:
    # 대사증후군 혈압 기준은 130/85 (고혈압 전단계 130/80과 다름)
    assert metabolic(diastolic_bp=84).criteria["blood_pressure"] is False
    assert metabolic(diastolic_bp=85).criteria["blood_pressure"] is True


def test_metabolic_diagnosis_replaces_medication() -> None:
    # 진단 "예"면 수치가 정상이어도 해당 (약 복용을 진단으로 대신)
    result = metabolic(htn=True, dm=True, waist_cm=95)
    assert result.criteria["blood_pressure"] is True
    assert result.criteria["fasting_glucose"] is True
    assert result.status == MetabolicSyndromeStatus.MET


def test_metabolic_unknown_when_missing_could_change_result() -> None:
    # 2개 해당 + 중성지방·HDL 없음 → 빠진 게 해당이면 MET, 아니면 NOT_MET → UNKNOWN
    result = metabolic(waist_cm=95, fasting_glucose=105, triglyceride=None, hdl_cholesterol=None)
    assert result.met_count == 2
    assert result.status == MetabolicSyndromeStatus.UNKNOWN


def test_metabolic_not_met_even_if_missing_all_true() -> None:
    # 해당 0개 + 2개 빠짐 → 빠진 게 다 해당이어도 2개 → NOT_MET
    result = metabolic(triglyceride=None, hdl_cholesterol=None)
    assert result.status == MetabolicSyndromeStatus.NOT_MET


def test_metabolic_blood_pressure_partial_value() -> None:
    # 수축기만 있고 정상 → 이완기를 몰라서 혈압 기준은 모름
    assert metabolic(diastolic_bp=None).criteria["blood_pressure"] is None
    # 수축기만 있고 해당 → 해당
    assert metabolic(systolic_bp=135, diastolic_bp=None).criteria["blood_pressure"] is True


def test_metabolic_without_checkup() -> None:
    # 유효한 검진이 없으면 수치 기준은 모두 모름, 진단만 반영
    no_dx = judge_metabolic_syndrome(None, Gender.MALE, is_hypertension_diagnosed=False, is_diabetes_diagnosed=False)
    both_dx = judge_metabolic_syndrome(None, Gender.MALE, is_hypertension_diagnosed=True, is_diabetes_diagnosed=True)
    assert no_dx.status == MetabolicSyndromeStatus.UNKNOWN
    assert both_dx.met_count == 2
    assert both_dx.status == MetabolicSyndromeStatus.UNKNOWN
