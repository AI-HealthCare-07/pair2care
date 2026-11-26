from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from ai_worker.tasks.daily_action_facts import gather_daily_action_facts, week_start
from app.models.health_logs import HealthLogType
from shared.tasks import KST


class DailyActionFactsTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.target = date(2024, 11, 25)  # 월요일, 실제 실행 날짜와 무관한 과거
        self.profile_repo = self.enterContext(
            patch("ai_worker.tasks.daily_action_facts.HealthProfileRepository")
        ).return_value
        self.walk_repo = self.enterContext(patch("ai_worker.tasks.daily_action_facts.HealthLogRepository")).return_value
        self.profile_repo.get_latest = AsyncMock(return_value=None)
        self.walk_repo.find_in_range = AsyncMock(return_value=None)

    async def test_missing_profile_and_record(self) -> None:
        self.assertEqual(await gather_daily_action_facts(7, self.target), {})
        self.profile_repo.get_latest.assert_awaited_once_with(7)
        current = datetime(2024, 11, 25, tzinfo=KST)
        calls = self.walk_repo.find_in_range.await_args_list
        self.assertEqual(calls[0].args, (7, HealthLogType.WALK_DAYS, current, current + timedelta(days=1)))
        self.assertEqual(calls[1].args, (7, HealthLogType.WALK_DAYS, current - timedelta(days=7), current))

    async def test_current_zero_is_evidence_and_does_not_fall_back(self) -> None:
        self.walk_repo.find_in_range.return_value = SimpleNamespace(value=Decimal("0"))
        self.profile_repo.get_latest.return_value = SimpleNamespace(
            is_hypertension_diagnosed=False, is_diabetes_diagnosed=False, smoking_current=8
        )
        facts = await gather_daily_action_facts(7, self.target)
        self.assertEqual(
            facts,
            {"is_hypertension_diagnosed": False, "is_diabetes_diagnosed": False, "has_zero_walk_days": True},
        )
        self.walk_repo.find_in_range.assert_awaited_once()

    async def test_current_nonzero_blocks_previous_zero(self) -> None:
        self.walk_repo.find_in_range.side_effect = [SimpleNamespace(value=Decimal("3")), SimpleNamespace(value=0)]
        self.assertEqual(await gather_daily_action_facts(7, self.target), {})
        self.walk_repo.find_in_range.assert_awaited_once()

    async def test_previous_zero_is_used_if_current_missing(self) -> None:
        self.walk_repo.find_in_range.side_effect = [None, SimpleNamespace(value=Decimal("0.00"))]
        self.assertEqual(await gather_daily_action_facts(7, self.target), {"has_zero_walk_days": True})

    async def test_smoking_codes(self) -> None:
        for code in (1, 2, 3, 8, 888, None):
            self.profile_repo.get_latest.return_value = SimpleNamespace(
                is_hypertension_diagnosed=False, is_diabetes_diagnosed=True, smoking_current=code
            )
            facts = await gather_daily_action_facts(7, self.target)
            self.assertEqual(facts.get("is_current_smoker", False), code in (1, 2))
            self.assertTrue(facts["is_diabetes_diagnosed"])

    def test_kst_week_boundary(self) -> None:
        self.assertEqual(week_start(date(2024, 11, 24)), datetime(2024, 11, 18, tzinfo=KST))
        self.assertEqual(week_start(date(2024, 11, 25)), datetime(2024, 11, 25, tzinfo=KST))
