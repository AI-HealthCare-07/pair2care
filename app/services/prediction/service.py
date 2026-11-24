"""예측 흐름 (api.md 5-0): 설문 저장 직후 FastAPI 안에서 바로 추론하고 질환별 risk_predictions 저장."""

from datetime import date
from typing import Any

from tortoise.transactions import in_transaction

from app.models.checkup_records import CheckupRecord
from app.models.health_profiles import HealthProfile
from app.models.risk_predictions import PredictionMethod, RiskPrediction
from app.models.users import User
from app.repositories.health_profile_repository import to_answer_values
from app.repositories.risk_prediction_repository import RiskPredictionRepository
from app.services.prediction.criteria import CheckupValues, judge_checkup
from app.services.prediction.features import build_input_snapshot
from app.services.prediction.model import load_model, to_level, to_score
from app.services.prediction.plan import PredictionPlan


class PredictionService:
    def __init__(self) -> None:
        self.prediction_repo = RiskPredictionRepository()

    async def predict(
        self, user: User, profile: HealthProfile, plan: PredictionPlan, age: int, surveyed_on: date
    ) -> list[RiskPrediction]:
        """plan.diseases마다 MODEL 행, 유효한 검진이 있으면 같은 질환에 CHECKUP_CRITERIA 행도 저장."""
        if not plan.diseases:
            return []

        snapshot = build_input_snapshot(user.gender.value, age, to_answer_values(profile))

        async with in_transaction() as conn:
            checkup = await self.prediction_repo.get_latest_checkup(user.id, using_db=conn)
            judgements = {
                judgement.disease: judgement
                for judgement in judge_checkup(to_checkup_values(checkup), reference_on=surveyed_on)
            }

            rows: list[RiskPrediction] = []
            for disease in plan.diseases:
                model = load_model(disease)
                score = to_score(model.probability(snapshot["model_inputs"]))
                rows.append(
                    await self.prediction_repo.create(
                        using_db=conn,
                        user_id=user.id,
                        health_profile_id=profile.id,
                        disease=disease,
                        method=PredictionMethod.MODEL,
                        score=score,
                        level=to_level(score),
                        factors=model.factors(snapshot["model_inputs"]),
                        model_version=model.model_version,
                        input_snapshot=snapshot,
                    )
                )
                judgement = judgements.get(disease)
                if judgement is not None and checkup is not None:
                    rows.append(
                        await self.prediction_repo.create(
                            using_db=conn,
                            user_id=user.id,
                            health_profile_id=profile.id,
                            checkup_record_id=checkup.id,
                            disease=disease,
                            method=PredictionMethod.CHECKUP_CRITERIA,
                            level=judgement.level,
                            input_snapshot=judgement.input_snapshot,
                        )
                    )
        return rows


def to_checkup_values(checkup: CheckupRecord | None) -> CheckupValues | None:
    if checkup is None:
        return None
    return CheckupValues(
        checked_on=checkup.checked_on,
        systolic_bp=checkup.systolic_bp,
        diastolic_bp=checkup.diastolic_bp,
        fasting_glucose=checkup.fasting_glucose,
        hba1c=checkup.hba1c,
        waist_cm=checkup.waist_cm,
        triglyceride=checkup.triglyceride,
        hdl_cholesterol=checkup.hdl_cholesterol,
    )


def summarize(prediction: RiskPrediction) -> dict[str, Any]:
    """3-1 응답 predictions 한 줄 (상세는 5장 조회 API)."""
    return {
        "id": prediction.id,
        "disease": prediction.disease.value,
        "method": prediction.method.value,
        "score": prediction.score,
        "level": prediction.level.value,
    }
