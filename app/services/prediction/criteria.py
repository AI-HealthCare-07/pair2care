"""검진 수치 기준표 판정 (api.md 5-1).

검진 수치는 모델 입력에 넣지 않고 이 기준표로만 판정한다.
- 고혈압·당뇨: LOW / CAUTION / HIGH, 판정할 수 없으면 None (→ 기준표 행을 만들지 않음)
- 대사증후군: MET / NOT_MET / UNKNOWN, 저장하지 않고 조회할 때마다 계산

DB·모델과 상관없는 순수 함수만 둔다. 예측 흐름(service)에서 불러 씀.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from dateutil.relativedelta import relativedelta

from app.models.risk_predictions import Disease, RiskLevel
from app.models.users import Gender

# 기준표가 바뀌면 올림 → 판정 행의 input_snapshot에 같이 남겨 어느 기준으로 판정했는지 추적
CRITERIA_VERSION = "2026-11-19"

# 검진 수치는 예측 시점 기준 이 기간 안의 것만 씀 (api.md 5-1 유효기간)
CHECKUP_VALID_PERIOD = relativedelta(years=1)

Number = int | float | Decimal


class MetabolicSyndromeStatus(StrEnum):
    MET = "MET"  # 5개 중 3개 이상 해당
    NOT_MET = "NOT_MET"  # 빠진 항목이 모두 해당이어도 3개 미만
    UNKNOWN = "UNKNOWN"  # 빠진 항목 때문에 판단 불가


@dataclass(frozen=True, slots=True)
class CheckupValues:
    """판정에 쓰는 검진 수치. 없는 값은 None (checkup_records 컬럼과 같은 이름)."""

    checked_on: date
    systolic_bp: Number | None = None
    diastolic_bp: Number | None = None
    fasting_glucose: Number | None = None
    hba1c: Number | None = None
    waist_cm: Number | None = None
    triglyceride: Number | None = None
    hdl_cholesterol: Number | None = None


@dataclass(frozen=True, slots=True)
class CriteriaJudgement:
    """기준표 행 하나 (method = CHECKUP_CRITERIA)에 들어갈 값."""

    disease: Disease
    level: RiskLevel
    input_snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MetabolicSyndromeResult:
    status: MetabolicSyndromeStatus
    met_count: int  # 해당하는 기준 수
    criteria: dict[str, bool | None]  # 기준별 해당 여부 (None = 값이 없어 모름)


def _to_decimal(value: Number | None) -> Decimal | None:
    # float 5.7과 Decimal("5.7")을 그대로 비교하면 5.7이 기준 미만으로 나옴 → 문자열을 거쳐 Decimal로 맞춤
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class _Threshold:
    field: str
    caution: Decimal  # 이 값 이상이면 CAUTION (전단계 이상)
    high: Decimal  # 이 값 이상이면 HIGH (질환 범위)


# 대한고혈압학회·대한당뇨병학회 진료지침 (api.md 5-1 표)
_THRESHOLDS: dict[Disease, tuple[_Threshold, ...]] = {
    Disease.HYPERTENSION: (
        _Threshold("systolic_bp", caution=Decimal("130"), high=Decimal("140")),
        _Threshold("diastolic_bp", caution=Decimal("80"), high=Decimal("90")),
    ),
    Disease.DIABETES: (
        _Threshold("fasting_glucose", caution=Decimal("100"), high=Decimal("126")),
        _Threshold("hba1c", caution=Decimal("5.7"), high=Decimal("6.5")),
    ),
}


def is_checkup_valid(checked_on: date, reference_on: date) -> bool:
    """검진이 예측 시점 기준 1년 안인지.

    reference_on보다 늦은 검진(설문 뒤에 검진을 넣은 경우)도 유효로 봄.
    """
    return checked_on >= reference_on - CHECKUP_VALID_PERIOD


def judge_disease(disease: Disease, checkup: CheckupValues) -> RiskLevel | None:
    """한 질환을 기준표로 판정. 판정할 수 없으면 None.

    - 있는 값 중 하나라도 기준 이상이면 그 값으로 판정 (가장 높은 단계)
    - LOW는 그 질환 항목이 모두 있고 모두 정상일 때만
    - 그 외(있는 값은 정상인데 빠진 항목이 있거나, 값이 하나도 없음)는 None
      → 일부 수치만으로 "정상"을 내면 빠진 수치가 높은 사람을 안심시킬 수 있어서
    """
    thresholds = _THRESHOLDS[disease]
    values = [_to_decimal(getattr(checkup, t.field)) for t in thresholds]

    if any(v is not None and v >= t.high for v, t in zip(values, thresholds, strict=True)):
        return RiskLevel.HIGH
    if any(v is not None and v >= t.caution for v, t in zip(values, thresholds, strict=True)):
        return RiskLevel.CAUTION
    if all(v is not None for v in values):
        return RiskLevel.LOW
    return None


def build_criteria_snapshot(disease: Disease, checkup: CheckupValues) -> dict[str, Any]:
    """기준표 행의 input_snapshot. 검진 기록을 지워도 판정 근거가 남도록 값 자체를 담음."""
    snapshot: dict[str, Any] = {"checked_on": checkup.checked_on.isoformat(), "criteria_version": CRITERIA_VERSION}
    for threshold in _THRESHOLDS[disease]:
        value = getattr(checkup, threshold.field)
        if value is not None:
            # JSON 컬럼에 넣을 수 있게 Decimal은 float로 (소수 첫째 자리 값이라 손실 없음)
            snapshot[threshold.field] = float(value) if isinstance(value, Decimal) else value
    return snapshot


def judge_checkup(checkup: CheckupValues | None, reference_on: date) -> list[CriteriaJudgement]:
    """검진 1건으로 판정 가능한 질환만 기준표 결과를 돌려줌.

    검진이 없거나 유효기간이 지났으면 빈 목록 (모델 행만 저장).
    진단 "예"인 질환 제외는 호출하는 쪽(service)에서 함.
    """
    if checkup is None or not is_checkup_valid(checkup.checked_on, reference_on):
        return []

    judgements: list[CriteriaJudgement] = []
    for disease in Disease:
        level = judge_disease(disease, checkup)
        if level is not None:
            judgements.append(
                CriteriaJudgement(
                    disease=disease, level=level, input_snapshot=build_criteria_snapshot(disease, checkup)
                )
            )
    return judgements


def _at_least(value: Number | None, threshold: Decimal) -> bool | None:
    v = _to_decimal(value)
    return None if v is None else v >= threshold


def _below(value: Number | None, threshold: Decimal) -> bool | None:
    v = _to_decimal(value)
    return None if v is None else v < threshold


def _either(first: bool | None, second: bool | None) -> bool | None:
    """둘 중 하나라도 해당이면 해당, 둘 다 해당 아님이면 해당 아님, 그 외는 모름."""
    if first is True or second is True:
        return True
    if first is False and second is False:
        return False
    return None


def judge_metabolic_syndrome(
    checkup: CheckupValues | None,
    gender: Gender,
    *,
    is_hypertension_diagnosed: bool,
    is_diabetes_diagnosed: bool,
) -> MetabolicSyndromeResult:
    """대사증후군 판정 (수정 NCEP-ATP III + 대한비만학회 허리둘레 기준).

    checkup은 유효기간 안의 가장 최근 검진 (없으면 None).
    약 복용은 진단 여부로 대신하고, 이상지질혈증 약은 설문에 없어 중성지방·HDL은 수치로만 판정.
    허리둘레는 검진 값만 씀 (설문 허리둘레는 기록용).
    """
    is_male = gender == Gender.MALE
    values = checkup or CheckupValues(checked_on=date.min)

    if is_hypertension_diagnosed:
        blood_pressure: bool | None = True
    else:
        blood_pressure = _either(
            _at_least(values.systolic_bp, Decimal("130")), _at_least(values.diastolic_bp, Decimal("85"))
        )

    if is_diabetes_diagnosed:
        glucose: bool | None = True
    else:
        glucose = _at_least(values.fasting_glucose, Decimal("100"))

    criteria: dict[str, bool | None] = {
        "waist": _at_least(values.waist_cm, Decimal("90") if is_male else Decimal("85")),
        "triglyceride": _at_least(values.triglyceride, Decimal("150")),
        "hdl_cholesterol": _below(values.hdl_cholesterol, Decimal("40") if is_male else Decimal("50")),
        "blood_pressure": blood_pressure,
        "fasting_glucose": glucose,
    }

    met_count = sum(1 for v in criteria.values() if v is True)
    unknown_count = sum(1 for v in criteria.values() if v is None)

    if met_count >= 3:
        status = MetabolicSyndromeStatus.MET
    elif met_count + unknown_count < 3:
        status = MetabolicSyndromeStatus.NOT_MET
    else:
        status = MetabolicSyndromeStatus.UNKNOWN

    return MetabolicSyndromeResult(status=status, met_count=met_count, criteria=criteria)
