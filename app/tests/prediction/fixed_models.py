"""테스트용 고정 모델: 모델 파일(model_files/)이 진짜 JSON으로 바뀌어도 API 테스트가 깨지지 않게 함.

계수는 0이고 절편만 있어서 입력과 상관없이 당뇨 34 / 고혈압 21 (api.md 3-1 예시 점수).
API 테스트 클래스에 @patch(LOAD_MODEL_TARGET, new=fixed_model)로 씌워서 씀.
"""

import math
from typing import Final

from app.models.risk_predictions import Disease
from app.services.prediction.features import FEATURE_NAMES
from app.services.prediction.health_age import ITEM_FIELDS_BY_DISEASE, SexMeans
from app.services.prediction.model import LogisticModel

LOAD_MODEL_TARGET: Final = "app.services.prediction.service.load_model"
FIXED_SCORE_BY_DISEASE: Final = {Disease.DIABETES: 34, Disease.HYPERTENSION: 21}


def fixed_model(disease: Disease) -> LogisticModel:
    probability = FIXED_SCORE_BY_DISEASE[disease] / 100
    return LogisticModel(
        model_version=f"{disease.lower()}_risk:fixed",
        disease=disease,
        intercept=math.log(probability / (1 - probability)),
        coefficients=dict.fromkeys(FEATURE_NAMES, 0.0),
        means=dict.fromkeys(FEATURE_NAMES, 0.0),
    )


LOAD_SEX_MEANS_TARGET: Final = "app.services.prediction.service.load_sex_means"
LOAD_ARCHIVED_MODEL_TARGET: Final = "app.services.prediction.service.load_archived_model"
LOAD_ARCHIVED_SEX_MEANS_TARGET: Final = "app.services.prediction.service.load_archived_sex_means"
EXPLAIN_BMI_MEAN: Final = 24.3  # api.md 3-1 예시 답(172.5cm·78.2kg)의 bmi는 26.3 → 평균보다 2.0 높음


def explain_model(disease: Disease) -> LogisticModel:
    """건강 나이·요인 API 테스트용: 나이 계수 0.05, bmi 계수 0.1 → bmi 2.0 높으면 +4살. 다른 문항 계수는 0.

    점수는 나이에 따라 바뀌므로 이 모델을 쓰는 테스트는 점수를 확인하지 않음.
    """
    coefficients = dict.fromkeys(FEATURE_NAMES, 0.0) | {"age": 0.05, "bmi": 0.1}
    return LogisticModel(
        model_version=f"{disease.lower()}_risk:explain",
        disease=disease,
        intercept=-6.0,
        coefficients=coefficients,
        means=dict.fromkeys(FEATURE_NAMES, 0.0),
    )


def explain_sex_means(disease: Disease) -> SexMeans:
    """explain_model과 같은 버전의 같은 성별 평균 (bmi만 24.3, 나머지 0)."""
    means = dict.fromkeys(ITEM_FIELDS_BY_DISEASE[disease], 0.0) | {"bmi": EXPLAIN_BMI_MEAN}
    return SexMeans(model_version=f"{disease.lower()}_risk:explain", means={"MALE": means, "FEMALE": means})
