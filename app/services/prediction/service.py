"""예측 흐름 (api.md 5-0): 설문 저장 직후 FastAPI 안에서 바로 추론하고 질환별 risk_predictions 저장."""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from tortoise.transactions import in_transaction

from app.core import default_logger as logger
from app.models.checkup_records import CheckupRecord
from app.models.health_profiles import HealthProfile
from app.models.risk_predictions import PredictionMethod, RiskPrediction
from app.models.users import User
from app.repositories.health_profile_repository import HealthProfileRepository, to_answer_values
from app.repositories.risk_prediction_repository import RiskPredictionRepository
from app.services.prediction.criteria import CheckupValues, is_checkup_valid, judge_checkup, judge_metabolic_syndrome
from app.services.prediction.features import build_input_snapshot, calculate_age
from app.services.prediction.health_age import NOT_EXPLAINED, RowExplanation, explain_row, load_sex_means
from app.services.prediction.model import load_model, to_level, to_score
from app.services.prediction.plan import PredictionPlan, plan_predictions
from app.services.prediction.simulation import SimulationChanges, apply_changes, check_simulatable_keys
from app.services.prediction.views import (
    build_detail,
    metabolic_to_response,
    pick_latest_rows,
    summarize_row,
)

KST = ZoneInfo("Asia/Seoul")


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

    async def retry_latest(self, user: User) -> dict[str, Any]:
        """5-5 다시 계산: 최근 설문에 모델 예측이 없을 때(3-1 예측 실패)만 설문 날짜 기준으로 다시 예측."""
        profile = await HealthProfileRepository().get_latest(user.id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SURVEY_DETAIL)

        surveyed_on = profile.created_at.astimezone(KST).date()
        age = calculate_age(user.birthday, surveyed_on)
        plan = plan_predictions(
            age=age,
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )
        existing = await self.prediction_repo.list_for_profile(profile.id)
        if plan.diseases and any(row.method == PredictionMethod.MODEL for row in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_PREDICTED_DETAIL)

        try:
            rows = await self.predict(user, profile, plan, age, surveyed_on)
        except Exception as error:
            logger.exception("다시 계산 실패 health_profile_id=%s", profile.id)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=RETRY_FAILED_DETAIL) from error
        return {
            "predictions": [summarize(row) for row in rows],
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
        }

    async def repredict_latest(self, user: User) -> dict[str, Any]:
        """4-1·4-4: 최근 설문 + 지금 가장 최근 검진으로 다시 예측. 응답은 3-1과 같은 예측 필드.

        설문이 없으면 예측하지 않음 (나중에 3-1을 저장할 때 이 검진을 읽어서 같이 판정).
        예측이 실패해도 검진은 이미 저장됨 → prediction_error: true.
        """
        profile = await HealthProfileRepository().get_latest(user.id)
        if profile is None:
            return {"predictions": [], "managed_diseases": [], "skipped_reason": None, "prediction_error": False}

        today = datetime.now(KST).date()
        age = calculate_age(user.birthday, today)
        plan = plan_predictions(
            age=age,
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )
        predictions: list[dict[str, Any]] = []
        prediction_error = False
        try:
            predictions = [summarize(row) for row in await self.predict(user, profile, plan, age, today)]
        except Exception:
            logger.exception("검진 저장 뒤 예측 실패 health_profile_id=%s", profile.id)
            prediction_error = True
        return {
            "predictions": predictions,
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
            "prediction_error": prediction_error,
        }


def explain_of(row: RiskPrediction) -> RowExplanation:
    """모델 행의 건강 나이 + 요인 가감 나이 (api.md 5-0·5-2·5-3, #114). 조회 때 input_snapshot으로 계산.

    means_by_sex가 없거나 어긋났거나 다른 모델 버전이면 둘 다 None → 건강 나이 null, 요인은 저장값(years null).
    계산 중 오류가 나도 점수·단계는 그대로 보여 주도록 에러 로그만 남김 (건강정보 대신 행 id만).
    """
    if row.method != PredictionMethod.MODEL:
        return NOT_EXPLAINED
    try:
        return explain_row(row, load_model(row.disease), load_sex_means(row.disease))
    except (KeyError, TypeError, ValueError):
        logger.exception("건강 나이·요인 계산 실패 risk_prediction_id=%s", row.id)
        return NOT_EXPLAINED


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


NO_SURVEY_DETAIL = "아직 설문 기록이 없어요."
ALREADY_PREDICTED_DETAIL = "이미 계산된 위험도가 있어요."
RETRY_FAILED_DETAIL = "위험도를 계산하지 못했어요. 잠시 후 다시 시도해 주세요."
PREDICTION_NOT_FOUND_DETAIL = "예측 결과를 찾을 수 없어요."


class PredictionQueryService:
    """5-2·5-3 조회."""

    def __init__(self) -> None:
        self.prediction_repo = RiskPredictionRepository()
        self.health_profile_repo = HealthProfileRepository()

    async def get_latest(self, user: User) -> dict[str, Any]:
        """5-2. 최근 설문 기준 질환별 최근 예측 + 대사증후군 (유효한 검진이 없으면 null)."""
        profile = await self.health_profile_repo.get_latest(user.id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SURVEY_DETAIL)

        surveyed_on = profile.created_at.astimezone(KST).date()
        plan = plan_predictions(
            age=calculate_age(user.birthday, surveyed_on),
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )
        rows = pick_latest_rows(await self.prediction_repo.list_for_profile(profile.id))

        checkup = await self.prediction_repo.get_latest_checkup(user.id)
        today = datetime.now(KST).date()
        metabolic = None
        if checkup is not None and is_checkup_valid(checkup.checked_on, today):
            metabolic = judge_metabolic_syndrome(
                to_checkup_values(checkup),
                user.gender,
                is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
                is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
            )

        return {
            "health_profile_id": profile.id,
            "predictions": [summarize_row(row, explain_of(row).health_age) for row in rows],
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
            "metabolic_syndrome": metabolic_to_response(metabolic),
        }

    async def get_detail(self, user: User, prediction_id: int) -> dict[str, Any]:
        """5-3. 남의 것이면 404."""
        row = await self.prediction_repo.get_for_user(user.id, prediction_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PREDICTION_NOT_FOUND_DETAIL)
        previous = None
        if row.method == PredictionMethod.MODEL:
            previous = await self.prediction_repo.get_previous_model_row(row)
        explanation = explain_of(row)
        return build_detail(row, previous, explanation.health_age, explanation.factors)

    async def simulate(self, user: User, raw_changes: dict[str, Any]) -> dict[str, Any]:
        """5-4. 최근 설문에 바꾼 습관만 덮어 다시 계산 (저장 안 함). 검사 순서: 필드 400 → 형식 422 → 해당 여부 400."""
        check_simulatable_keys(raw_changes)
        try:
            changes = SimulationChanges.model_validate(raw_changes)
        except ValidationError as error:
            raise RequestValidationError(error.errors(include_url=False)) from None

        profile = await self.health_profile_repo.get_latest(user.id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SURVEY_DETAIL)

        survey = to_answer_values(profile)
        simulated = apply_changes(survey, changes)

        surveyed_on = profile.created_at.astimezone(KST).date()
        age = calculate_age(user.birthday, surveyed_on)
        plan = plan_predictions(
            age=age,
            is_pregnant=profile.is_pregnant,
            is_hypertension_diagnosed=profile.is_hypertension_diagnosed,
            is_diabetes_diagnosed=profile.is_diabetes_diagnosed,
        )

        saved = {
            row.disease: row
            for row in pick_latest_rows(await self.prediction_repo.list_for_profile(profile.id))
            if row.method == PredictionMethod.MODEL
        }
        before_inputs = build_input_snapshot(user.gender.value, age, survey)["model_inputs"]
        after_inputs = build_input_snapshot(user.gender.value, age, simulated)["model_inputs"]

        results = []
        for disease in plan.diseases:
            model = load_model(disease)
            saved_row = saved.get(disease)
            # before = 저장된 최근 MODEL 점수. 없거나(예측 실패 등) 지금 모델과 버전이 다르면(가짜 → 진짜 교체)
            # 같은 모델로 비교해야 하므로 최근 설문으로 그 자리에서 계산
            before_score = None
            if saved_row is not None and saved_row.model_version == model.model_version:
                before_score = saved_row.score
            if before_score is None:
                before_score = to_score(model.probability(before_inputs))
            after_score = to_score(model.probability(after_inputs))
            results.append(
                {
                    "disease": disease.value,
                    "before": {"score": before_score, "level": to_level(before_score).value},
                    "after": {"score": after_score, "level": to_level(after_score).value},
                }
            )

        return {
            "results": results,
            "managed_diseases": [disease.value for disease in plan.managed_diseases],
            "skipped_reason": plan.skipped_reason.value if plan.skipped_reason else None,
        }
