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
        self.target = date(2024, 11, 25)
        self.current = week_start(self.target)
        self.profile_repo = self.enterContext(
            patch("ai_worker.tasks.daily_action_facts.HealthProfileRepository")
        ).return_value
        self.walk_repo = self.enterContext(patch("ai_worker.tasks.daily_action_facts.HealthLogRepository")).return_value
        self.profile_repo.get_latest = AsyncMock(return_value=None)
        self.records: dict[tuple[HealthLogType, datetime], SimpleNamespace] = {}
        self.walk_repo.find_in_range = AsyncMock(side_effect=self._find_record)

    async def _find_record(
        self, user_id: int, log_type: HealthLogType, start: datetime, end: datetime
    ) -> SimpleNamespace | None:
        self.assertEqual(user_id, 7)
        self.assertLess(start, end)
        return self.records.get((log_type, start))

    def _record(self, log_type: HealthLogType, value: str, *, previous: bool = False, value2: str | None = None) -> None:
        start = self.current - timedelta(days=7) if previous else self.current
        self.records[log_type, start] = SimpleNamespace(
            value=Decimal(value), value2=Decimal(value2) if value2 is not None else None
        )

    def _profile(self, **overrides: object) -> SimpleNamespace:
        values = {
            "is_hypertension_diagnosed": False,
            "is_diabetes_diagnosed": False,
            "smoking_current": 8,
            "alcohol_ever": 1,
            "alcohol_frequency": 8,
        }
        return SimpleNamespace(**(values | overrides))

    async def test_missing_profile_and_record(self) -> None:
        self.assertEqual(await gather_daily_action_facts(7, self.target), {})
        self.profile_repo.get_latest.assert_awaited_once_with(7)
        calls = self.walk_repo.find_in_range.await_args_list
        self.assertEqual(calls[0].args, (7, HealthLogType.WALK_DAYS, self.current, self.current + timedelta(days=1)))
        self.assertEqual(calls[1].args, (7, HealthLogType.WALK_DAYS, self.current - timedelta(days=7), self.current))

    async def test_current_zero_is_evidence_and_does_not_fall_back(self) -> None:
        self._record(HealthLogType.WALK_DAYS, "0")
        self.profile_repo.get_latest.return_value = self._profile()
        facts = await gather_daily_action_facts(7, self.target)
        self.assertEqual(
            facts,
            {"is_hypertension_diagnosed": False, "is_diabetes_diagnosed": False, "has_zero_walk_days": True},
        )
        self.assertEqual(
            sum(c.args[1] == HealthLogType.WALK_DAYS for c in self.walk_repo.find_in_range.await_args_list), 1
        )

    async def test_current_nonzero_blocks_previous_zero(self) -> None:
        self._record(HealthLogType.WALK_DAYS, "3")
        self._record(HealthLogType.WALK_DAYS, "0", previous=True)
        self.assertEqual(await gather_daily_action_facts(7, self.target), {"has_walk_days": True})

    async def test_previous_zero_is_used_if_current_missing(self) -> None:
        self._record(HealthLogType.WALK_DAYS, "0.00", previous=True)
        self.assertEqual(await gather_daily_action_facts(7, self.target), {"has_zero_walk_days": True})

    async def test_smoking_codes(self) -> None:
        for code in (1, 2, 3, 8, 888, None):
            self.profile_repo.get_latest.return_value = self._profile(smoking_current=code, is_diabetes_diagnosed=True)
            facts = await gather_daily_action_facts(7, self.target)
            self.assertEqual(facts.get("is_current_smoker", False), code in (1, 2))
            self.assertTrue(facts["is_diabetes_diagnosed"])

    async def test_alcohol_codes(self) -> None:
        for code in (1, 2, 3, 4, 5, 6, 8, 888, None):
            self.profile_repo.get_latest.return_value = self._profile(alcohol_ever=2, alcohol_frequency=code)
            facts = await gather_daily_action_facts(7, self.target)
            self.assertEqual(facts.get("has_reported_alcohol", False), code in (2, 3, 4, 5, 6))
        self.profile_repo.get_latest.return_value = self._profile(alcohol_ever=1, alcohol_frequency=6)
        self.assertNotIn("has_reported_alcohol", await gather_daily_action_facts(7, self.target))

    async def test_weekly_fallback_is_per_type_and_strength_boundary(self) -> None:
        self._record(HealthLogType.WALK_DAYS, "4")
        self._record(HealthLogType.STRENGTH_DAYS, "1", previous=True)
        self._record(HealthLogType.SLEEP, "6", previous=True, value2="8")
        self.assertEqual(
            await gather_daily_action_facts(7, self.target),
            {"has_walk_days": True, "has_fewer_strength_days": True, "has_sleep_record": True},
        )
        self._record(HealthLogType.STRENGTH_DAYS, "2")
        facts = await gather_daily_action_facts(7, self.target)
        self.assertNotIn("has_fewer_strength_days", facts)
        self.assertTrue(facts["has_sleep_record"])

    async def test_sleep_requires_complete_valid_record(self) -> None:
        self._record(HealthLogType.SLEEP, "7")
        self.assertNotIn("has_sleep_record", await gather_daily_action_facts(7, self.target))
        self._record(HealthLogType.SLEEP, "7", value2="25")
        self.assertNotIn("has_sleep_record", await gather_daily_action_facts(7, self.target))
        self._record(HealthLogType.SLEEP, "7", value2="8")
        self.assertTrue((await gather_daily_action_facts(7, self.target))["has_sleep_record"])

    def test_kst_week_boundary(self) -> None:
        self.assertEqual(week_start(date(2024, 11, 24)), datetime(2024, 11, 18, tzinfo=KST))
        self.assertEqual(week_start(date(2024, 11, 25)), datetime(2024, 11, 25, tzinfo=KST))
