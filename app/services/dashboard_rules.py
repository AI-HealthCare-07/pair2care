"""7장 대시보드 계산 (api.md 7-1~7-3). DB 없이 쓰는 순수 함수."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from app.models.health_logs import HealthLog, HealthLogType
from app.models.risk_predictions import Disease, PredictionMethod, RiskLevel, RiskPrediction
from app.services.health_log_rules import KST, RULES

DISEASE_ORDER: Final = (Disease.DIABETES, Disease.HYPERTENSION)
LEVEL_RANK: Final = {RiskLevel.LOW: 0, RiskLevel.CAUTION: 1, RiskLevel.HIGH: 2}
# 주간 합계가 의미 있는 기록 (한 주에 몇 잔·몇 분)
SUM_TYPES: Final = frozenset({HealthLogType.ALCOHOL, HealthLogType.EXERCISE})


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def kst_date(value: datetime) -> date:
    return value.astimezone(KST).date()


def round1(value: Decimal) -> float:
    """평균은 소수 첫째 자리, 0.05는 올림 (파이썬 round의 짝수 반올림을 쓰지 않음)."""
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def average(values: Sequence[Decimal]) -> float | None:
    if not values:
        return None
    return round1(sum(values, Decimal(0)) / len(values))


def is_newer(row: RiskPrediction, other: RiskPrediction) -> bool:
    return (row.created_at, row.id) > (other.created_at, other.id)


# ---------- 7-1 위험도 추이 ----------


def build_risk_trend(rows: Iterable[RiskPrediction], managed_diseases: Sequence[Disease]) -> list[dict[str, Any]]:
    """질환별 주(월~일, KST)마다 마지막 MODEL 예측 1개. 그 주 마지막 기준표 판정은 criteria_level로.

    기준표 행이 그 주 마지막 MODEL 행보다 오래됐으면 지난 판정이라 null (5-2 pick_latest_rows와 같은 규칙,
    가장 최근 검진을 지웠거나 1년이 지나 기준표 없이 다시 예측한 경우).

    관리 중(최근 설문에서 진단 "예")이면 points는 비움 → 화면은 "관리 중" 카드. 예측이 없는 주는 점을 뺌.
    """
    last_model: dict[tuple[Disease, date], RiskPrediction] = {}
    last_criteria: dict[tuple[Disease, date], RiskPrediction] = {}
    for row in rows:
        key = (row.disease, monday_of(kst_date(row.created_at)))
        target = last_model if row.method == PredictionMethod.MODEL else last_criteria
        current = target.get(key)
        if current is None or is_newer(row, current):
            target[key] = row

    series = []
    for disease in DISEASE_ORDER:
        is_managed = disease in managed_diseases
        points = []
        if not is_managed:
            weeks = sorted(week for (row_disease, week) in last_model if row_disease == disease)
            for week in weeks:
                model_row = last_model[(disease, week)]
                criteria_row = last_criteria.get((disease, week))
                if criteria_row is not None and is_newer(model_row, criteria_row):
                    criteria_row = None
                points.append(
                    {
                        "week_start": week.isoformat(),
                        "score": model_row.score,
                        "level": model_row.level.value,
                        "prediction_id": model_row.id,
                        "criteria_level": criteria_row.level.value if criteria_row else None,
                    }
                )
        series.append({"disease": disease.value, "managed": is_managed, "points": points})
    return series


# ---------- 7-2 항목별 그래프 ----------


def bucket_logs(rows: Sequence[HealthLog], log_type: HealthLogType, bucket: str) -> list[dict[str, Any]]:
    """raw: 그대로 / day·week: 평균 (혈압은 수축기·이완기 각각). 오래된 순."""
    has_value2 = RULES[log_type].value2 is not None
    if bucket == "raw":
        return [
            {
                "measured_at": row.measured_at.astimezone(KST).isoformat(),
                "value": round1(row.value),
                "value2": round1(row.value2) if row.value2 is not None else None,
                "count": 1,
            }
            for row in rows
        ]

    groups: dict[date, list[HealthLog]] = defaultdict(list)
    for row in rows:
        day = kst_date(row.measured_at)
        groups[monday_of(day) if bucket == "week" else day].append(row)
    return [
        {
            "date": key.isoformat(),
            "value": average([row.value for row in groups[key]]),
            "value2": average([row.value2 for row in groups[key] if row.value2 is not None]) if has_value2 else None,
            "count": len(groups[key]),
        }
        for key in sorted(groups)
    ]


# ---------- 7-3 요약 카드 ----------


def choose_priority_disease(
    latest_rows: Sequence[RiskPrediction], managed_diseases: Sequence[Disease]
) -> Disease | None:
    """먼저 보여줄 질환: 관리 중이면 그 질환 → 아니면 단계가 높은 쪽 → 같으면 점수가 높은 쪽 → 같으면 당뇨 먼저."""
    for disease in DISEASE_ORDER:
        if disease in managed_diseases:
            return disease
    if not latest_rows:
        return None
    best = max(
        latest_rows,
        key=lambda row: (LEVEL_RANK[row.level], row.score or 0, -DISEASE_ORDER.index(row.disease)),
    )
    return best.disease


def summarize_week_logs(rows: Sequence[HealthLog]) -> dict[str, Any]:
    """이번 주 일일 기록 요약. 기록이 없는 종류는 뺌.

    - 걸음 수·컨디션(하루 1행): days_logged, avg_value
    - 나머지: count, avg_value, (혈압) avg_value2, last_measured_at, (음주·운동) total_value
    """
    by_type: dict[HealthLogType, list[HealthLog]] = defaultdict(list)
    for row in rows:
        if not RULES[row.log_type].is_weekly:
            by_type[row.log_type].append(row)

    summary: dict[str, Any] = {}
    for log_type in HealthLogType:
        group = by_type.get(log_type)
        if not group:
            continue
        values = [row.value for row in group]
        if RULES[log_type].is_once_a_day:
            summary[log_type.value] = {"days_logged": len(group), "avg_value": average(values)}
            continue
        item: dict[str, Any] = {"count": len(group), "avg_value": average(values)}
        if RULES[log_type].value2 is not None:
            item["avg_value2"] = average([row.value2 for row in group if row.value2 is not None])
        if log_type in SUM_TYPES:
            item["total_value"] = round1(sum(values, Decimal(0)))
        item["last_measured_at"] = max(row.measured_at for row in group).astimezone(KST).isoformat()
        summary[log_type.value] = item
    return summary
