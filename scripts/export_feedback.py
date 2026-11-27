"""재학습용 (입력, 정답) 쌍 뽑기 (REQ-NFR-018, docs/feedback-loop.md).

새 테이블 없이 뽑는 순간에 기존 테이블에서 만듦:
  user_consents(MODEL_IMPROVEMENT 동의) + risk_predictions(MODEL 행 input_snapshot.inputs) + checkup_records
규칙 (#148, 11/27 지연·성은):
  - 동의: 가장 최근 동의 행이 "동의"일 때만, **그 시각 이후에 입력한** 설문·검진만 (철회 후 재동의면 마지막 동의 시각 이후)
  - 짝: 검진 1건마다 앞뒤 30일 안 가장 가까운 설문 1개 (같은 거리면 앞쪽). 같은 설문의 여러 MODEL 행은 첫 행만
  - 정답: 하나라도 기준 이상 → 1, 0은 수치가 둘 다 있고 둘 다 정상일 때만, 그 외는 쌍 안 만듦
  - 제외: @example.com 계정(데모·테스트), 탈퇴(비활성) 계정. 진단·임신·나이 밖은 원래 MODEL 행이 없음
출력: user_id 대신 순번만 쓴 CSV (레포·공개 저장소에 올리지 않음, 학습 끝나면 바로 지움). 로그엔 개수만.

실행 (서버, 데모 시드와 같은 방식): EXPORT_PATH=/tmp/feedback.csv uv run python -m scripts.export_feedback
"""

import asyncio
import csv
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from tortoise import Tortoise

from app.core import default_logger as logger
from app.core.db.databases import TORTOISE_ORM
from app.models.checkup_records import CheckupRecord
from app.models.risk_predictions import Disease, PredictionMethod, RiskPrediction
from app.models.user_consents import Agreement, UserConsent
from app.models.users import User
from app.services.health_log_rules import KST
from app.services.prediction.features import FEATURE_NAMES, to_model_inputs

FEEDBACK_AGREEMENT: Final = "MODEL_IMPROVEMENT"  # 지연님이 Agreement에 추가 예정 (선택 동의)
MAX_GAP_DAYS: Final = 30
TEST_EMAIL_DOMAIN: Final = "@example.com"
DEFAULT_EXPORT_PATH: Final = "/tmp/feedback_pairs.csv"
CSV_COLUMNS: Final = ("seq", "disease", *FEATURE_NAMES, "label", "gap_days")

SYSTOLIC_MIN: Final = 130
DIASTOLIC_MIN: Final = 80
FASTING_GLUCOSE_MIN: Final = 100
HBA1C_MIN: Final = Decimal("5.7")


@dataclass(frozen=True)
class CheckupValues:
    """정답에 쓰는 검진 수치 (없으면 None)."""

    checked_on: date
    systolic_bp: int | None = None
    diastolic_bp: int | None = None
    fasting_glucose: int | None = None
    hba1c: Decimal | None = None


@dataclass(frozen=True)
class SurveyCandidate:
    """짝 후보 설문 1개: 설문 시각과 질환별 첫 MODEL 행의 inputs(변환 전)."""

    surveyed_at: datetime
    inputs_by_disease: Mapping[Disease, Mapping[str, Any]]


@dataclass(frozen=True)
class FeedbackPair:
    disease: Disease
    model_inputs: Mapping[str, int | float]
    label: int
    gap_days: int


# ───── 규칙 (순수 함수) ─────
def is_at_least(value: int | Decimal | None, minimum: int | Decimal) -> bool:
    return value is not None and value >= minimum


def two_value_label(first_high: bool, second_high: bool, has_both: bool) -> int | None:
    """하나라도 기준 이상 → 1, 둘 다 있고 둘 다 정상 → 0, 그 외(하나만 있고 정상·둘 다 없음) → None."""
    if first_high or second_high:
        return 1
    return 0 if has_both else None


def hypertension_label(checkup: CheckupValues) -> int | None:
    return two_value_label(
        is_at_least(checkup.systolic_bp, SYSTOLIC_MIN),
        is_at_least(checkup.diastolic_bp, DIASTOLIC_MIN),
        checkup.systolic_bp is not None and checkup.diastolic_bp is not None,
    )


def diabetes_label(checkup: CheckupValues) -> int | None:
    return two_value_label(
        is_at_least(checkup.fasting_glucose, FASTING_GLUCOSE_MIN),
        is_at_least(checkup.hba1c, HBA1C_MIN),
        checkup.fasting_glucose is not None and checkup.hba1c is not None,
    )


LABELERS: Final = {Disease.DIABETES: diabetes_label, Disease.HYPERTENSION: hypertension_label}


def is_test_account(email: str) -> bool:
    return email.lower().endswith(TEST_EMAIL_DOMAIN)


def consented_since(consents: Iterable[tuple[int, datetime, bool]]) -> datetime | None:
    """(id, 시각, 동의 여부) 기록 중 가장 최근 행(id가 가장 큰 행, 2-6 조회와 같은 순서)이 동의면 그 시각.

    철회했거나 기록이 없으면 None. 같은 시각에 두 행이 있어도 id로 순서가 정해짐 (#162 지연 리뷰).
    """
    latest = max(consents, key=lambda consent: consent[0], default=None)
    if latest is None or not latest[2]:
        return None
    return latest[1]


def gap_days(checked_on: date, surveyed_at: datetime) -> int:
    return abs((checked_on - surveyed_at.astimezone(KST).date()).days)


def nearest_survey(
    checked_on: date, candidates: Sequence[SurveyCandidate], max_gap_days: int = MAX_GAP_DAYS
) -> tuple[SurveyCandidate, int] | None:
    """검진일과 가장 가까운 설문 (앞뒤 max_gap_days 안). 같은 거리면 앞쪽(먼저 한) 설문."""
    in_range = [(gap_days(checked_on, c.surveyed_at), c.surveyed_at, c) for c in candidates]
    in_range = [item for item in in_range if item[0] <= max_gap_days]
    if not in_range:
        return None
    gap, _, candidate = min(in_range, key=lambda item: (item[0], item[1]))
    return candidate, gap


def build_pairs(checkups: Iterable[CheckupValues], candidates: Sequence[SurveyCandidate]) -> list[FeedbackPair]:
    """한 사용자의 검진·설문 후보 → 쌍 목록. 검진 1건마다 질환별 최대 1쌍."""
    pairs = []
    for checkup in checkups:
        found = nearest_survey(checkup.checked_on, candidates)
        if found is None:
            continue
        candidate, gap = found
        for disease, inputs in candidate.inputs_by_disease.items():
            label = LABELERS[disease](checkup)
            if label is None:
                continue
            model_inputs = to_model_inputs(inputs["sex"], int(inputs["age"]), inputs)  # 학습과 같은 변환 (#68)
            pairs.append(FeedbackPair(disease=disease, model_inputs=model_inputs, label=label, gap_days=gap))
    return pairs


def candidates_from_rows(rows: Iterable[RiskPrediction], since: datetime) -> list[SurveyCandidate]:
    """MODEL 행 → 설문별 후보. 같은 설문·질환의 여러 행은 첫 행만, 설문 시각이 동의 전이면 뺌."""
    first_rows: dict[int, dict[Disease, RiskPrediction]] = {}
    for row in sorted(rows, key=lambda r: r.created_at):
        first_rows.setdefault(row.health_profile_id, {}).setdefault(row.disease, row)
    candidates = []
    for by_disease in first_rows.values():
        surveyed_at = min(row.created_at for row in by_disease.values())
        if surveyed_at < since:
            continue
        inputs = {disease: row.input_snapshot["inputs"] for disease, row in by_disease.items()}
        candidates.append(SurveyCandidate(surveyed_at=surveyed_at, inputs_by_disease=inputs))
    return candidates


def to_csv_rows(pairs: Iterable[FeedbackPair]) -> list[dict[str, Any]]:
    """user_id 없이 순번만. 같은 사람이 여러 줄이어도 연결할 수 없게 섞지 않고 순서대로 번호."""
    return [
        {"seq": seq, "disease": pair.disease.value, **pair.model_inputs, "label": pair.label, "gap_days": pair.gap_days}
        for seq, pair in enumerate(pairs, start=1)
    ]


# ───── DB 읽기 ─────
async def consent_times_by_user() -> dict[int, datetime]:
    """동의한 사용자 → 마지막 동의 시각. 동의 종류가 아직 없으면 빈 dict."""
    if FEEDBACK_AGREEMENT not in Agreement.__members__:
        logger.info("동의 종류 %s가 아직 없어서 뽑을 사용자가 없어요", FEEDBACK_AGREEMENT)
        return {}
    rows = await UserConsent.filter(agreement=Agreement(FEEDBACK_AGREEMENT)).values_list(
        "id", "user_id", "created_at", "is_agreed"
    )
    by_user: dict[int, list[tuple[int, datetime, bool]]] = {}
    for consent_id, user_id, created_at, is_agreed in rows:
        by_user.setdefault(user_id, []).append((consent_id, created_at, is_agreed))
    times = {user_id: consented_since(consents) for user_id, consents in by_user.items()}
    return {user_id: since for user_id, since in times.items() if since is not None}


async def pairs_for_user(user_id: int, since: datetime) -> list[FeedbackPair]:
    rows = await RiskPrediction.filter(user_id=user_id, method=PredictionMethod.MODEL)
    # 검진도 동의한 뒤에 입력한 것만 (검진일이 아니라 입력 시각 기준, #162 성은 리뷰)
    records = await CheckupRecord.filter(user_id=user_id, created_at__gte=since).order_by("checked_on")
    checkups = [CheckupValues(r.checked_on, r.systolic_bp, r.diastolic_bp, r.fasting_glucose, r.hba1c) for r in records]
    return build_pairs(checkups, candidates_from_rows(rows, since))


async def export(path: Path) -> dict[str, int]:
    consents = await consent_times_by_user()
    users = await User.filter(id__in=list(consents), is_active=True).values_list("id", "email")
    pairs: list[FeedbackPair] = []
    skipped_test = 0
    for user_id, email in users:
        if is_test_account(email):
            skipped_test += 1
            continue
        pairs.extend(await pairs_for_user(user_id, consents[user_id]))

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(to_csv_rows(pairs))
    return {
        "consented_users": len(consents),
        "skipped_test_accounts": skipped_test,
        "pairs_diabetes": sum(p.disease == Disease.DIABETES for p in pairs),
        "pairs_hypertension": sum(p.disease == Disease.HYPERTENSION for p in pairs),
    }


async def main() -> None:
    path = Path(os.environ.get("EXPORT_PATH", DEFAULT_EXPORT_PATH))
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        summary = await export(path)
    finally:
        await Tortoise.close_connections()
    logger.info("재학습 쌍 뽑기 완료 (%s): %s", path, summary)  # 개수만, 건강정보는 로그에 안 남김


if __name__ == "__main__":
    asyncio.run(main())
