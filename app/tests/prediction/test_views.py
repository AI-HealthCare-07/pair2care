"""5-2·5-3 응답 만들기 (DB 없이 도는 순수 테스트)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from app.models.risk_predictions import Disease, PredictionMethod
from app.services.prediction.criteria import MetabolicSyndromeResult, MetabolicSyndromeStatus
from app.services.prediction.views import find_changed_inputs, metabolic_to_response, pick_latest_rows


def fake_row(row_id: int, disease: Disease, method: PredictionMethod, minute: int) -> Any:
    return SimpleNamespace(
        id=row_id, disease=disease, method=method, created_at=datetime(2026, 11, 24, 5, minute, tzinfo=UTC)
    )


def test_pick_latest_rows_one_per_disease_and_method_in_order() -> None:
    rows = [
        fake_row(1, Disease.HYPERTENSION, PredictionMethod.MODEL, 0),
        fake_row(2, Disease.DIABETES, PredictionMethod.MODEL, 0),
        fake_row(3, Disease.DIABETES, PredictionMethod.CHECKUP_CRITERIA, 5),  # 검진 저장으로 나중에 생긴 행
        fake_row(4, Disease.DIABETES, PredictionMethod.CHECKUP_CRITERIA, 9),
    ]

    picked = pick_latest_rows(rows)

    assert [row.id for row in picked] == [2, 4, 1]  # 당뇨 MODEL → 당뇨 기준표(최신) → 고혈압 MODEL


def test_changed_inputs_compare_survey_values_only() -> None:
    before = {"weight_kg": 80.0, "alcohol_frequency": 5, "sex": "MALE", "age": 45}
    after = {"weight_kg": 78.2, "alcohol_frequency": 5, "sex": "MALE", "age": 46}

    # 나이가 바뀐 건 변화로 안 보임
    assert find_changed_inputs(before, after) == [{"feature": "weight_kg", "before": 80.0, "after": 78.2}]


def test_metabolic_response_lists_missing() -> None:
    result = MetabolicSyndromeResult(
        status=MetabolicSyndromeStatus.UNKNOWN,
        met_count=2,
        criteria={
            "waist": True,
            "triglyceride": None,
            "hdl_cholesterol": None,
            "blood_pressure": True,
            "fasting_glucose": False,
        },
    )

    assert metabolic_to_response(result) == {
        "status": "UNKNOWN",
        "met_count": 2,
        "missing": ["triglyceride", "hdl_cholesterol"],
    }
    assert metabolic_to_response(None) is None


def test_criteria_row_older_than_latest_model_row_is_hidden() -> None:
    # 가장 최근 검진을 지우고 기준표 없이 다시 예측 → 지난 판정은 5-2에서 숨김
    rows = [
        fake_row(1, Disease.DIABETES, PredictionMethod.MODEL, 0),
        fake_row(2, Disease.DIABETES, PredictionMethod.CHECKUP_CRITERIA, 0),
        fake_row(3, Disease.DIABETES, PredictionMethod.MODEL, 10),  # 다시 예측 (기준표 없음)
    ]

    assert [row.id for row in pick_latest_rows(rows)] == [3]
