"""설문 저장 뒤 어떤 질환을 예측할지 정함 (api.md 3-1 "처리 순서" 2번·응답 201).

- 진단 "예"인 질환은 예측하지 않고 managed_diseases (S-09 "관리 중" 카드)
- 임신 중이면 두 질환 모두 예측 안 함 (모델이 임신부를 빼고 학습) → skipped_reason PREGNANT
- 나이가 학습 범위(30~69세) 밖이면 예측 안 함 → skipped_reason AGE_OUT_OF_RANGE
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.services.prediction.criteria import Disease
from app.services.prediction.features import is_age_in_range

# 응답 predictions 순서 (api.md 3-1 예시: 당뇨 → 고혈압)
DISEASE_ORDER = (Disease.DIABETES, Disease.HYPERTENSION)


class SkippedReason(StrEnum):
    PREGNANT = "PREGNANT"
    AGE_OUT_OF_RANGE = "AGE_OUT_OF_RANGE"


@dataclass(frozen=True)
class PredictionPlan:
    diseases: list[Disease] = field(default_factory=list)  # 이번에 예측할 질환
    managed_diseases: list[Disease] = field(default_factory=list)
    skipped_reason: SkippedReason | None = None


def plan_predictions(
    *,
    age: int,
    is_pregnant: bool | None,
    is_hypertension_diagnosed: bool,
    is_diabetes_diagnosed: bool,
) -> PredictionPlan:
    diagnosed = {Disease.DIABETES: is_diabetes_diagnosed, Disease.HYPERTENSION: is_hypertension_diagnosed}
    managed = [disease for disease in DISEASE_ORDER if diagnosed[disease]]

    if is_pregnant:
        return PredictionPlan(managed_diseases=managed, skipped_reason=SkippedReason.PREGNANT)
    if not is_age_in_range(age):
        return PredictionPlan(managed_diseases=managed, skipped_reason=SkippedReason.AGE_OUT_OF_RANGE)
    targets = [disease for disease in DISEASE_ORDER if not diagnosed[disease]]
    return PredictionPlan(diseases=targets, managed_diseases=managed)
