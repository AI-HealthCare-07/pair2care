"""scripts/export_feedback.py: 재학습 쌍 규칙 (#148) — 순수 규칙은 DB 없이, 뽑기는 데모 시드(가상 데이터)로."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tortoise.contrib.test import TestCase

from app.models.checkup_records import CheckupRecord
from app.models.risk_predictions import Disease
from app.services.health_log_rules import KST
from app.services.prediction.features import FEATURE_NAMES
from scripts.export_feedback import (
    CSV_COLUMNS,
    CheckupValues,
    FeedbackPair,
    SurveyCandidate,
    build_pairs,
    consented_since,
    diabetes_label,
    export,
    hypertension_label,
    is_test_account,
    nearest_survey,
    pairs_for_user,
    to_csv_rows,
)
from scripts.seed_demo import seed

DAY = date(2026, 11, 20)
INPUTS = {
    "sex": "MALE",
    "age": 52,
    "height_cm": 172.0,
    "weight_kg": 80.0,
    "father_diabetes_history": 0,
    "mother_diabetes_history": 0,
    "sibling_diabetes_history": 0,
    "father_hypertension_history": 1,
    "mother_hypertension_history": 0,
    "sibling_hypertension_history": 0,
    "alcohol_frequency": 3,
    "alcohol_amount": 2,
    "smoking_current": 1,
}


def at(day: date, hour: int = 10) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=KST)


def survey(day: date, hour: int = 10) -> SurveyCandidate:
    return SurveyCandidate(at(day, hour), {Disease.DIABETES: INPUTS, Disease.HYPERTENSION: INPUTS})


# ───── 정답: 하나라도 넘으면 1, 0은 둘 다 있고 둘 다 정상일 때만 ─────
def test_hypertension_label() -> None:
    assert hypertension_label(CheckupValues(DAY, 130, 70)) == 1
    assert hypertension_label(CheckupValues(DAY, 120, 80)) == 1
    assert hypertension_label(CheckupValues(DAY, 131, None)) == 1  # 하나만 있어도 넘으면 1
    assert hypertension_label(CheckupValues(DAY, 129, 79)) == 0
    assert hypertension_label(CheckupValues(DAY, 120, None)) is None  # 하나만 있고 정상 → 쌍 안 만듦
    assert hypertension_label(CheckupValues(DAY)) is None


def test_diabetes_label() -> None:
    assert diabetes_label(CheckupValues(DAY, fasting_glucose=100)) == 1
    assert diabetes_label(CheckupValues(DAY, hba1c=Decimal("5.7"))) == 1
    assert diabetes_label(CheckupValues(DAY, fasting_glucose=99, hba1c=Decimal("5.6"))) == 0
    # 공복혈당만 정상: 국건영에선 이런 사람의 13.7%가 당화혈색소로 실제 1 → 0으로 두지 않음 (성은)
    assert diabetes_label(CheckupValues(DAY, fasting_glucose=90)) is None
    assert diabetes_label(CheckupValues(DAY, hba1c=Decimal("5.2"))) is None


# ───── 동의·제외 ─────
def test_consented_since_uses_latest_row() -> None:
    first, withdrawn, again = at(DAY), at(DAY + timedelta(days=1)), at(DAY + timedelta(days=2))
    assert consented_since([(1, first, True)]) == first
    assert consented_since([(1, first, True), (2, withdrawn, False)]) is None
    assert consented_since([(3, again, True), (1, first, True), (2, withdrawn, False)]) == again  # 재동의 → 마지막
    assert consented_since([]) is None


def test_consented_since_same_time_uses_id_order() -> None:
    # 같은 시각에 동의·철회가 찍혀도 id가 큰 행(나중 행)이 기준
    moment = at(DAY)
    assert consented_since([(5, moment, True), (6, moment, False)]) is None
    assert consented_since([(6, moment, True), (5, moment, False)]) == moment


def test_is_test_account() -> None:
    assert is_test_account("demo@example.com") and is_test_account("A@Example.COM")
    assert not is_test_account("someone@gmail.com")


# ───── 짝 고르기: 검진마다 앞뒤 30일 안 가장 가까운 설문, 같은 거리면 앞쪽 ─────
def test_nearest_survey_picks_closest_within_30_days() -> None:
    before, after = survey(DAY - timedelta(days=5)), survey(DAY + timedelta(days=2))
    assert nearest_survey(DAY, [before, after]) == (after, 2)
    assert nearest_survey(DAY, [survey(DAY - timedelta(days=31))]) is None
    assert nearest_survey(DAY, [survey(DAY + timedelta(days=30))]) is not None


def test_nearest_survey_tie_prefers_earlier() -> None:
    before, after = survey(DAY - timedelta(days=3)), survey(DAY + timedelta(days=3))
    assert nearest_survey(DAY, [after, before]) == (before, 3)


def test_nearest_survey_uses_kst_date() -> None:
    # 11/19 23:30 KST 설문 = 11/19 → 11/20 검진과 1일 차이 (UTC로 보면 같은 날이 아님에 주의)
    late_night = SurveyCandidate(at(DAY - timedelta(days=1), 23).replace(minute=30), {})
    assert nearest_survey(DAY, [late_night]) == (late_night, 1)


def test_build_pairs_one_pair_per_checkup_and_disease() -> None:
    checkups = [
        CheckupValues(DAY, 136, 86, fasting_glucose=90),  # 고혈압 1, 당뇨는 하나만 있고 정상 → 없음
        CheckupValues(DAY + timedelta(days=60), 120, 75, 95, Decimal("5.4")),  # 30일 안에 설문 없음 → 없음
    ]
    pairs = build_pairs(checkups, [survey(DAY - timedelta(days=1)), survey(DAY - timedelta(days=7))])
    assert [(p.disease, p.label, p.gap_days) for p in pairs] == [(Disease.HYPERTENSION, 1, 1)]
    assert list(pairs[0].model_inputs) == list(FEATURE_NAMES)  # 학습과 같은 12개 입력


def test_csv_rows_have_sequence_not_user() -> None:
    pair = FeedbackPair(Disease.DIABETES, dict.fromkeys(FEATURE_NAMES, 0), 1, 3)
    rows = to_csv_rows([pair, pair])
    assert [row["seq"] for row in rows] == [1, 2]
    assert set(rows[0]) == set(CSV_COLUMNS) and "user_id" not in rows[0]


# ───── DB에서 뽑기 (데모 시드 가상 사용자) ─────
class TestExportFeedback(TestCase):
    async def test_pairs_for_user_from_seed(self) -> None:
        now = datetime(2026, 11, 26, 10, 0, tzinfo=KST)
        summary = await seed(now, "Demo1234!")
        checkup = await CheckupRecord.get(user_id=summary.user_id)

        pairs = await pairs_for_user(summary.user_id, since=now - timedelta(days=365))

        # 시드 검진 136/86 → 고혈압 1, 공복혈당 104 → 당뇨 1 (당화혈색소 없어도 넘었으니 1)
        assert sorted((p.disease.value, p.label) for p in pairs) == [("DIABETES", 1), ("HYPERTENSION", 1)]
        assert all(p.gap_days <= 30 for p in pairs)
        assert checkup.checked_on <= now.date()

    async def test_pairs_exclude_surveys_before_consent(self) -> None:
        now = datetime(2026, 11, 26, 10, 0, tzinfo=KST)
        summary = await seed(now, "Demo1234!")
        assert await pairs_for_user(summary.user_id, since=now + timedelta(days=1)) == []

    async def test_checkup_entered_before_consent_is_excluded(self) -> None:
        # 검진 입력 → 동의 → 그 뒤 설문만 있어도, 동의 전에 입력한 검진은 쌍이 안 됨
        now = datetime(2026, 11, 26, 10, 0, tzinfo=KST)
        summary = await seed(now, "Demo1234!")
        checkup = await CheckupRecord.get(user_id=summary.user_id)
        assert await pairs_for_user(summary.user_id, since=checkup.created_at + timedelta(seconds=1)) == []

    async def test_export_without_consent_type_writes_header_only(self) -> None:
        # MODEL_IMPROVEMENT가 Agreement에 추가되기 전에는 뽑을 사용자가 없음 (지연님 작업 뒤 자동으로 동작)
        path = Path(self._testMethodName + ".csv")
        try:
            summary = await export(path)
            assert summary["pairs_diabetes"] == summary["pairs_hypertension"] == 0
            assert path.read_text(encoding="utf-8").splitlines() == [",".join(CSV_COLUMNS)]
        finally:
            path.unlink(missing_ok=True)
