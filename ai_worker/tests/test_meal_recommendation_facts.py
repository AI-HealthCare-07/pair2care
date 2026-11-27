import json
import unittest
from unittest.mock import AsyncMock

from ai_worker.tasks.llm_recommendation import (
    MEAL_PROMPT_VERSION,
    NO_EVIDENCE,
    generate_recommendation,
    load_guides,
    retrieve_guides,
)
from ai_worker.tasks.meal_recommendation_facts import is_broth_model_label, is_non_broth_model_label


class MealRecommendationFactsTests(unittest.IsolatedAsyncioTestCase):
    def test_model_labels_from_erd(self) -> None:
        broth = (
            "갈비탕",
            "감자탕",
            "김치찌개",
            "냉면",
            "닭개장",
            "된장찌개",
            "떡만두국",
            "삼계탕",
            "설렁탕",
            "수제비",
            "순두부찌개",
            "육개장",
            "잔치국수",
            "짬뽕",
            "칼국수",
            "콩나물국",
        )
        for label in broth:
            with self.subTest(label=label):
                self.assertTrue(is_broth_model_label(label))
                self.assertFalse(is_non_broth_model_label(label))
        for label in ("간장게장", "닭볶음탕", "냉면_물냉면", "미등록", None):
            with self.subTest(label=label):
                self.assertFalse(is_broth_model_label(label))
                self.assertEqual(is_non_broth_model_label(label), label in ("간장게장", "닭볶음탕"))

    def test_sodium_boundary_and_missing(self) -> None:
        guides = load_guides()
        for sodium, expected in ((0, False), (664.9, False), (665, True), (666.9, True), (667, True), (900, True)):
            with self.subTest(sodium=sodium):
                ids = {
                    guide.id
                    for guide in retrieve_guides(
                        "MEAL_ALTERNATIVE", {"is_broth_dish": True, "sodium_mg": sodium}, guides
                    )
                }
                self.assertEqual("htn_less_salt" in ids, expected)
        self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", {"is_broth_dish": True}, guides), [])

    async def test_below_threshold_abstains_without_model(self) -> None:
        result = await generate_recommendation("MEAL_ALTERNATIVE", {"is_broth_dish": True, "sodium_mg": 664.9})
        self.assertEqual(result.content, NO_EVIDENCE)
        self.assertEqual(result.prompt_version, MEAL_PROMPT_VERSION)
        self.assertFalse(result.called_model)

    async def test_known_non_broth_sodium_candidate(self) -> None:
        selector = AsyncMock()
        selector.choose.return_value = ("meal_less_salty_seasoning", {"input_tokens": 7})
        result = await generate_recommendation(
            "MEAL_ALTERNATIVE",
            {"is_non_broth_dish": True, "is_broth_dish": False, "sodium_mg": 665},
            selector=selector,
        )
        self.assertTrue(result.called_model)
        self.assertIn("연하게", result.content)
        prompt, ids = selector.choose.await_args.args
        self.assertEqual(ids, ["meal_less_salty_seasoning"])
        self.assertNotIn("is_non_broth_dish", prompt)
        self.assertEqual(json.loads(prompt)["meal_facts"], {"sodium_mg": 665})

    def test_non_broth_boundary_and_unknown_labels(self) -> None:
        guides = load_guides()
        for label in ("간장게장", "닭볶음탕", "미등록", None):
            for sodium in (None, 664.9, 665, 900):
                with self.subTest(label=label, sodium=sodium):
                    facts = {
                        "is_broth_dish": is_broth_model_label(label),
                        "is_non_broth_dish": is_non_broth_model_label(label),
                        "sodium_mg": sodium,
                    }
                    ids = {g.id for g in retrieve_guides("MEAL_ALTERNATIVE", facts, guides)}
                    expected = (
                        {"meal_less_salty_seasoning"}
                        if label in ("간장게장", "닭볶음탕") and sodium is not None and sodium >= 665
                        else set()
                    )
                    self.assertEqual(ids, expected)
                    self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", {**facts, "is_drink": True}, guides), [])

    def test_non_broth_and_daily_regression(self) -> None:
        guides = load_guides()
        self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", {"is_broth_dish": False, "sodium_mg": 900}, guides), [])
        daily_ids = {
            guide.id for guide in retrieve_guides("DAILY_ACTION", {"is_hypertension_diagnosed": True}, guides)
        }
        self.assertIn("htn_less_salt", daily_ids)
        self.assertNotIn("meal_less_salty_seasoning", daily_ids)
