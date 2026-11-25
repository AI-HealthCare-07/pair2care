"""5장 조회 응답 만들기 (api.md 5-2·5-3). DB 없이 쓰는 순수 함수."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models.risk_predictions import PredictionMethod, RiskPrediction
from app.services.prediction.criteria import MetabolicSyndromeResult
from app.services.prediction.features import SURVEY_INPUT_FIELDS
from app.services.prediction.plan import DISEASE_ORDER

KST = ZoneInfo("Asia/Seoul")
# 기준표 input_snapshot에서 수치가 아닌 키
CRITERIA_META_KEYS = frozenset({"checked_on", "criteria_version"})


def to_kst_iso(value: datetime) -> str:
    return value.astimezone(KST).isoformat()


def summarize_row(row: RiskPrediction, health_age: dict[str, Any] | None = None) -> dict[str, Any]:
    """5-2 predictions 한 줄. checkup_record_id는 기준표 행에만, health_age는 모든 행에 (기준표 행은 항상 null)."""
    body: dict[str, Any] = {
        "id": row.id,
        "disease": row.disease.value,
        "method": row.method.value,
        "score": row.score,
        "level": row.level.value,
    }
    if row.method == PredictionMethod.CHECKUP_CRITERIA:
        body["checkup_record_id"] = row.checkup_record_id
    body["health_age"] = health_age
    body["created_at"] = to_kst_iso(row.created_at)
    return body


def pick_latest_rows(rows: Iterable[RiskPrediction]) -> list[RiskPrediction]:
    """질환별 가장 최근 MODEL 1개 + CHECKUP_CRITERIA 1개, 당뇨 → 고혈압, MODEL → 기준표 순서."""
    latest: dict[tuple[str, str], RiskPrediction] = {}
    for row in rows:
        key = (row.disease.value, row.method.value)
        current = latest.get(key)
        if current is None or (row.created_at, row.id) > (current.created_at, current.id):
            latest[key] = row
    # 기준표 행은 최신 MODEL 행과 같은 예측 때 만든 것만 (예측은 항상 MODEL → 기준표 순서로 같이 저장).
    # 최신 MODEL 행보다 오래됐으면 지난 판정 → 숨김 (가장 최근 검진을 지웠거나 1년이 지나 기준표 없이 다시 예측한 경우)
    for disease in DISEASE_ORDER:
        model_row = latest.get((disease.value, PredictionMethod.MODEL.value))
        criteria_row = latest.get((disease.value, PredictionMethod.CHECKUP_CRITERIA.value))
        if model_row is not None and criteria_row is not None:
            if (criteria_row.created_at, criteria_row.id) < (model_row.created_at, model_row.id):
                del latest[(disease.value, PredictionMethod.CHECKUP_CRITERIA.value)]

    keys = [
        (disease.value, method.value)
        for disease in DISEASE_ORDER
        for method in (PredictionMethod.MODEL, PredictionMethod.CHECKUP_CRITERIA)
    ]
    return [latest[key] for key in keys if key in latest]


def metabolic_to_response(result: MetabolicSyndromeResult | None) -> dict[str, Any] | None:
    """5-2 metabolic_syndrome. missing = 값이 없어 판단 못 한 기준."""
    if result is None:
        return None
    return {
        "status": result.status.value,
        "met_count": result.met_count,
        "missing": [name for name, value in result.criteria.items() if value is None],
    }


def find_changed_inputs(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    """설문 값 11개만 비교 (sex·age 제외 — 생일이 지나도 변화로 안 보이게). 변환 전 값 그대로."""
    return [
        {"feature": field, "before": before.get(field), "after": after.get(field)}
        for field in SURVEY_INPUT_FIELDS
        if before.get(field) != after.get(field)
    ]


def stored_factors(row: RiskPrediction) -> list[dict[str, Any]]:
    """예측 때 저장한 factors(옛 기준)를 years 없이. 같은 성별 평균을 못 쓸 때만 (api.md 5-3)."""
    return [{**factor, "years": None} for factor in (row.factors or [])]


def build_detail(
    row: RiskPrediction,
    previous: RiskPrediction | None,
    health_age: dict[str, Any] | None = None,
    factors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """5-3 예측 상세. 기준표 행은 factors·changed_inputs·previous 대신 판정 수치.

    factors: 조회 때 계산한 가감 나이 요인 (#114). None이면 저장된 factors를 years: null로 (방향만).
    """
    body: dict[str, Any] = {
        "id": row.id,
        "disease": row.disease.value,
        "method": row.method.value,
        "score": row.score,
        "level": row.level.value,
        "factors": None,
        "model_version": row.model_version,
        "changed_inputs": None,
        "previous": None,
        "health_age": health_age,
    }
    if row.method == PredictionMethod.CHECKUP_CRITERIA:
        snapshot = row.input_snapshot
        body["used_values"] = {key: value for key, value in snapshot.items() if key not in CRITERIA_META_KEYS}
        body["checked_on"] = snapshot.get("checked_on")
    else:
        body["factors"] = factors if factors is not None else stored_factors(row)
        if previous is not None:
            body["changed_inputs"] = find_changed_inputs(
                previous.input_snapshot.get("inputs", {}), row.input_snapshot.get("inputs", {})
            )
            body["previous"] = {
                "id": previous.id,
                "score": previous.score,
                "level": previous.level.value,
                "created_at": to_kst_iso(previous.created_at),
            }
    body["created_at"] = to_kst_iso(row.created_at)
    return body
