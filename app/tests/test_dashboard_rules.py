"""7장 대시보드 계산 (DB 없이 도는 순수 테스트)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.health_logs import HealthLog, HealthLogType
from app.models.health_profiles import SurveyKind
from app.models.risk_predictions import Disease, PredictionMethod, RiskLevel, RiskPrediction
from app.services.dashboard_rules import (
    bucket_logs,
    build_risk_trend,
    choose_priority_disease,
    round1,
    summarize_week_logs,
)
from app.services.health_log_rules import KST


def prediction(
    row_id: int, disease: Disease, when: datetime, score: int | None = 34, **overrides: Any
) -> RiskPrediction:
    values: dict[str, Any] = {
        "id": row_id,
        "user_id": 1,
        "health_profile_id": 1,
        "disease": disease,
        "method": PredictionMethod.MODEL,
        "score": score,
        "level": RiskLevel.CAUTION,
        "input_snapshot": {},
        "created_at": when,
    }
    values.update(overrides)
    return RiskPrediction(**values)


def log(row_id: int, log_type: HealthLogType, when: datetime, value: str, value2: str | None = None) -> HealthLog:
    return HealthLog(
        id=row_id,
        user_id=1,
        log_type=log_type,
        value=Decimal(value),
        value2=Decimal(value2) if value2 else None,
        measured_at=when,
        created_at=when,
    )


def kst(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=KST)  # 11/16(월)~22(일), 11/23(월)~29(일)


def test_trend_last_model_row_per_week_with_criteria_level() -> None:
    rows = [
        prediction(1, Disease.DIABETES, kst(17), score=40, level=RiskLevel.CAUTION),
        prediction(2, Disease.DIABETES, kst(19), score=37),  # 같은 주 마지막
        prediction(
            3, Disease.DIABETES, kst(19, 10), score=None, method=PredictionMethod.CHECKUP_CRITERIA, level=RiskLevel.HIGH
        ),
        prediction(4, Disease.DIABETES, kst(24), score=30),
        prediction(5, Disease.HYPERTENSION, kst(24), score=21, level=RiskLevel.LOW),
    ]

    series = build_risk_trend(rows, managed_diseases=[])

    diabetes, hypertension = series
    assert [(p["week_start"], p["score"], p["prediction_id"], p["criteria_level"]) for p in diabetes["points"]] == [
        ("2026-11-16", 37, 2, "HIGH"),
        ("2026-11-23", 30, 4, None),
    ]
    assert hypertension == {
        "disease": "HYPERTENSION",
        "managed": False,
        "points": [
            {
                "week_start": "2026-11-23",
                "score": 21,
                "level": "LOW",
                "prediction_id": 5,
                "criteria_level": None,
                "survey_kind": None,
            }
        ],
    }


def test_trend_hides_criteria_older_than_last_model_row_in_week() -> None:
    # 검진 저장으로 MODEL+기준표 → 같은 주에 최근 검진을 지워서 기준표 없이 다시 예측 (#103)
    rows = [
        prediction(1, Disease.DIABETES, kst(17), score=40),
        prediction(
            2, Disease.DIABETES, kst(17), score=None, method=PredictionMethod.CHECKUP_CRITERIA, level=RiskLevel.HIGH
        ),
        prediction(3, Disease.DIABETES, kst(18), score=35),
    ]

    diabetes, _ = build_risk_trend(rows, managed_diseases=[])

    assert [(p["prediction_id"], p["criteria_level"]) for p in diabetes["points"]] == [(3, None)]


def test_trend_managed_disease_has_no_points_and_both_diseases_always_listed() -> None:
    series = build_risk_trend([prediction(1, Disease.HYPERTENSION, kst(17))], managed_diseases=[Disease.HYPERTENSION])

    assert series == [
        {"disease": "DIABETES", "managed": False, "points": []},
        {"disease": "HYPERTENSION", "managed": True, "points": []},
    ]


def test_trend_week_is_kst_monday() -> None:
    # 11/22(일) 23:30 KST = 11/22 14:30 UTC → 11/16 주. UTC로 주를 나누면 안 됨
    series = build_risk_trend([prediction(1, Disease.DIABETES, kst(22, 23))], managed_diseases=[])

    assert series[0]["points"][0]["week_start"] == "2026-11-16"


def test_bucket_day_averages_each_side_of_blood_pressure() -> None:
    rows = [
        log(1, HealthLogType.BLOOD_PRESSURE, kst(18, 7), "130", "82"),
        log(2, HealthLogType.BLOOD_PRESSURE, kst(18, 21), "133", "84"),
        log(3, HealthLogType.BLOOD_PRESSURE, kst(19, 7), "128", "80"),
    ]

    points = bucket_logs(rows, HealthLogType.BLOOD_PRESSURE, "day")

    assert points == [
        {"date": "2026-11-18", "value": 131.5, "value2": 83.0, "count": 2},
        {"date": "2026-11-19", "value": 128.0, "value2": 80.0, "count": 1},
    ]


def test_bucket_week_and_raw() -> None:
    rows = [log(1, HealthLogType.WEIGHT, kst(17), "70.4"), log(2, HealthLogType.WEIGHT, kst(24), "69.9")]

    assert bucket_logs(rows, HealthLogType.WEIGHT, "week") == [
        {"date": "2026-11-16", "value": 70.4, "value2": None, "count": 1},
        {"date": "2026-11-23", "value": 69.9, "value2": None, "count": 1},
    ]
    raw = bucket_logs(rows, HealthLogType.WEIGHT, "raw")
    assert raw[0] == {"measured_at": "2026-11-17T09:00:00+09:00", "value": 70.4, "value2": None, "count": 1}


def test_round_half_up() -> None:
    assert round1(Decimal("131.25")) == 131.3  # 파이썬 round는 131.2
    assert round1(Decimal("6120")) == 6120.0


def test_priority_managed_first_then_level_then_score() -> None:
    low_diabetes = prediction(1, Disease.DIABETES, kst(24), score=50, level=RiskLevel.CAUTION)
    high_hypertension = prediction(2, Disease.HYPERTENSION, kst(24), score=40, level=RiskLevel.HIGH)
    caution_hypertension = prediction(3, Disease.HYPERTENSION, kst(24), score=55, level=RiskLevel.CAUTION)

    assert choose_priority_disease([low_diabetes], [Disease.HYPERTENSION]) == Disease.HYPERTENSION
    assert choose_priority_disease([low_diabetes, high_hypertension], []) == Disease.HYPERTENSION  # 단계 먼저
    assert choose_priority_disease([low_diabetes, caution_hypertension], []) == Disease.HYPERTENSION  # 점수
    same = prediction(4, Disease.HYPERTENSION, kst(24), score=50, level=RiskLevel.CAUTION)
    assert choose_priority_disease([low_diabetes, same], []) == Disease.DIABETES  # 같으면 당뇨 먼저
    assert choose_priority_disease([], []) is None


def test_week_summary_per_type() -> None:
    rows = [
        log(1, HealthLogType.BLOOD_PRESSURE, kst(24, 7), "130", "82"),
        log(2, HealthLogType.BLOOD_PRESSURE, kst(25, 7), "133", "85"),
        log(3, HealthLogType.STEPS, kst(24, 21), "6000"),
        log(4, HealthLogType.STEPS, kst(25, 21), "6240"),
        log(5, HealthLogType.ALCOHOL, kst(24, 22), "2"),
        log(6, HealthLogType.ALCOHOL, kst(26, 22), "3.5"),
        log(7, HealthLogType.WALK_DAYS, kst(23, 0), "3"),  # 주간 기록은 요약에서 뺌
    ]

    summary = summarize_week_logs(rows)

    assert summary == {
        "BLOOD_PRESSURE": {
            "count": 2,
            "avg_value": 131.5,
            "avg_value2": 83.5,
            "last_measured_at": "2026-11-25T07:00:00+09:00",
        },
        "ALCOHOL": {"count": 2, "avg_value": 2.8, "total_value": 5.5, "last_measured_at": "2026-11-26T22:00:00+09:00"},
        "STEPS": {"days_logged": 2, "avg_value": 6120.0},
    }


def test_trend_point_carries_survey_kind_for_edit_label() -> None:
    # 마이에서 고친 설문(EDIT)으로 다시 계산한 점은 화면이 "수정"으로 표시 (정할 것 1번)
    row = prediction(1, Disease.DIABETES, kst(17))
    row.health_profile_id = 7

    diabetes, _ = build_risk_trend([row], managed_diseases=[], kind_by_profile_id={7: SurveyKind.EDIT})
    unknown, _ = build_risk_trend([row], managed_diseases=[])

    assert diabetes["points"][0]["survey_kind"] == "EDIT"
    assert unknown["points"][0]["survey_kind"] is None
