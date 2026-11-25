"""테스트용 고정 모델: 모델 파일(model_files/)이 진짜 JSON으로 바뀌어도 API 테스트가 깨지지 않게 함.

계수는 0이고 절편만 있어서 입력과 상관없이 당뇨 34 / 고혈압 21 (api.md 3-1 예시 점수).
API 테스트 클래스에 @patch(LOAD_MODEL_TARGET, new=fixed_model)로 씌워서 씀.
"""

import math
from typing import Final

from app.models.risk_predictions import Disease
from app.services.prediction.features import FEATURE_NAMES
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
