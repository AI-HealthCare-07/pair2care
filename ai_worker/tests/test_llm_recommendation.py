import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ai_worker.tasks.llm_recommendation import (
    NO_EVIDENCE,
    AnthropicSelector,
    ClaudeCallError,
    clean_facts,
    generate_recommendation,
    load_guides,
    retrieve_guides,
)


class FakeSelector:
    def __init__(self, selected_id=None):
        self.selected_id = selected_id
        self.calls = 0

    async def choose(self, prompt, allowed_ids):
        self.calls += 1
        assert "@example.com" not in prompt
        return self.selected_id or allowed_ids[0], {"input_tokens": 30, "output_tokens": 12}


class RecommendationTests(unittest.IsolatedAsyncioTestCase):
    def test_decimal_as_numeric(self):
        self.assertEqual(clean_facts({"portion": Decimal("0.5")}), {"portion": 0.5})

    def test_filter_personal_identifiers(self):
        facts = clean_facts(
            {
                "email": "abc@example.com",
                "name": "실명",
                "phone_number": "010-1234-5678",
                "is_hypertension_diagnosed": True,
                "sodium_mg": 800,
                "meal_name": "국밥",
                "notes": "진료기록 내용",
            }
        )
        self.assertEqual(facts, {"is_hypertension_diagnosed": True, "sodium_mg": 800})

    def test_retrieval_by_recommendation_type(self):
        guides = load_guides()
        selected = retrieve_guides("MEAL_ALTERNATIVE", {"sodium_mg": 900, "is_broth_dish": True}, guides)
        self.assertTrue(selected)
        self.assertTrue(all("MEAL_ALTERNATIVE" in g.topics for g in selected))
        self.assertTrue(all(g.id != "htn_movement" for g in selected))

    async def test_no_data_abstains_without_api(self):
        selector = FakeSelector()
        result = await generate_recommendation("DAILY_ACTION", {}, selector=selector)
        self.assertEqual(result.content, NO_EVIDENCE)
        self.assertFalse(result.called_model)
        self.assertEqual(result.sources, [])
        self.assertEqual(selector.calls, 0)

    async def test_output_uses_verified_source_not_model_text(self):
        selector = FakeSelector("htn_less_salt")
        facts = {"is_hypertension_diagnosed": True, "email": "abc@example.com"}
        result = await generate_recommendation("DAILY_ACTION", facts, selector=selector)
        self.assertEqual(selector.calls, 1)
        self.assertEqual(result.content, "다음 식사에서 국물 음식이 있다면 국물을 조금 남겨 보는 건 어때요? [1]")
        self.assertEqual(result.sources[0]["number"], 1)
        self.assertTrue(result.sources[0]["url"].startswith("https://health.kdca.go.kr/"))
        self.assertEqual(result.input_tokens, 30)
        self.assertEqual(result.output_tokens, 12)

    async def test_reject_invalid_source_id(self):
        with self.assertRaises(ValueError):
            await generate_recommendation(
                "MEAL_ALTERNATIVE", {"sodium_mg": 1200, "is_broth_dish": True}, selector=FakeSelector("invented_source")
            )

    async def test_missing_relevant_evidence(self):
        result = await generate_recommendation("DAILY_ACTION", {"height_cm": 168}, selector=FakeSelector())
        self.assertEqual(result.content, NO_EVIDENCE)

    async def test_non_meal_guide_excluded(self):
        guide = load_guides()[0]
        custom = [replace(guide, topics=("DAILY_ACTION",))]
        result = await generate_recommendation(
            "MEAL_ALTERNATIVE", {"sodium_mg": 1200, "is_broth_dish": True}, selector=FakeSelector(), guides=custom
        )
        self.assertEqual(result.content, NO_EVIDENCE)

    async def test_negative_and_unrelated_facts_do_not_trigger_guides(self):
        for facts in (
            {"is_diabetes_diagnosed": 0, "is_hypertension_diagnosed": False},
            {"is_hypertension_diagnosed": "someone@example.com"},
        ):
            selector = FakeSelector()
            result = await generate_recommendation("DAILY_ACTION", facts, selector=selector)
            self.assertEqual(result.content, NO_EVIDENCE)
            self.assertEqual(selector.calls, 0)

    async def test_prevention_for_negative_diagnoses_with_walk_signal(self):
        selector = AsyncMock()
        selector.choose.return_value = ("prevention_walk", {"input_tokens": 7})
        facts = {
            "is_hypertension_diagnosed": False,
            "is_diabetes_diagnosed": False,
            "has_zero_walk_days": True,
            "walk_days": 0,
            "sodium_mg": 900,
            "memo": "private memo",
            "email": "private@example.com",
        }
        result = await generate_recommendation("DAILY_ACTION", facts, selector=selector)
        selector.choose.assert_awaited_once()
        prompt, ids = selector.choose.await_args.args
        payload = json.loads(prompt)
        self.assertEqual(payload["meal_facts"], {})
        self.assertIn("prevention_walk", ids)
        for private in ("walk_days", "sodium_mg", "diagnosed", "private", "has_zero_walk_days"):
            self.assertNotIn(private, prompt)
        self.assertTrue(result.called_model)
        self.assertEqual(
            result.sources[0]["url"],
            "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5293",
        )

    async def test_prevention_signals_are_daily_only(self):
        facts = {"has_zero_walk_days": True, "is_current_smoker": True}
        guides = load_guides()
        daily = retrieve_guides("DAILY_ACTION", facts, guides)
        self.assertEqual({guide.id for guide in daily}, {"prevention_walk", "prevention_tobacco_support"})
        self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", facts, guides), [])

    async def test_missing_or_false_walk_signal_abstains(self):
        for facts in ({"has_zero_walk_days": False}, {"walk_days": 0}, {"has_zero_walk_days": "0"}):
            selector = FakeSelector()
            result = await generate_recommendation("DAILY_ACTION", facts, selector=selector)
            self.assertEqual(result.content, NO_EVIDENCE)
            self.assertEqual(selector.calls, 0)

    async def test_general_prevention_candidates_and_privacy(self):
        expected = {
            "has_walk_days": "prevention_keep_walking",
            "has_fewer_strength_days": "prevention_strength_plan",
            "has_sleep_record": "prevention_sleep_routine",
            "has_reported_alcohol": "prevention_alcohol_plan",
        }
        for signal, guide_id in expected.items():
            selector = AsyncMock()
            selector.choose.return_value = (guide_id, {})
            facts = {"is_hypertension_diagnosed": False, "is_diabetes_diagnosed": False, signal: True}
            result = await generate_recommendation("DAILY_ACTION", facts, selector=selector)
            self.assertTrue(result.called_model)
            prompt, allowed = selector.choose.await_args.args
            self.assertEqual(allowed, [guide_id])
            self.assertNotIn(signal, prompt)
            self.assertEqual(json.loads(prompt)["meal_facts"], {})
            self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", facts, load_guides()), [])

    async def test_anthropic_adapter_parses_response_and_rejects_unknown_id(self):
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"selected_id":"verified"}')],
            usage=SimpleNamespace(input_tokens=9, output_tokens=4, cache_read_input_tokens=2),
        )
        create = AsyncMock(return_value=response)
        sdk = MagicMock()
        sdk.return_value.__aenter__.return_value = SimpleNamespace(messages=SimpleNamespace(create=create))
        with (
            patch.dict(sys.modules, {"anthropic": SimpleNamespace(AsyncAnthropic=sdk)}),
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-only"}),
        ):
            selector = AnthropicSelector()
            selected, usage = await selector.choose("mock prompt", ["verified"])
            self.assertEqual(selected, "verified")
            self.assertEqual(usage["cache_read_tokens"], 2)
            self.assertEqual(create.await_args.kwargs["messages"][0]["content"], "mock prompt")
            self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)
            with self.assertRaises(ClaudeCallError):
                await selector.choose("mock prompt", ["different"])


if __name__ == "__main__":
    unittest.main()
