import unittest

from ai_worker.tasks.llm_recommendation import (
    MEAL_PROMPT_VERSION,
    NO_EVIDENCE,
    generate_recommendation,
    load_guides,
    retrieve_guides,
)
from ai_worker.tasks.meal_recommendation_facts import is_broth_model_label


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
        for label in ("간장게장", "닭볶음탕", "냉면_물냉면", "미등록", None):
            with self.subTest(label=label):
                self.assertFalse(is_broth_model_label(label))

    def test_sodium_boundary_and_missing(self) -> None:
        guides = load_guides()
        for sodium, expected in ((0, False), (666, False), (666.9, False), (667, True), (900, True)):
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
        result = await generate_recommendation("MEAL_ALTERNATIVE", {"is_broth_dish": True, "sodium_mg": 666})
        self.assertEqual(result.content, NO_EVIDENCE)
        self.assertEqual(result.prompt_version, MEAL_PROMPT_VERSION)
        self.assertFalse(result.called_model)

    def test_non_broth_and_daily_regression(self) -> None:
        guides = load_guides()
        self.assertEqual(retrieve_guides("MEAL_ALTERNATIVE", {"is_broth_dish": False, "sodium_mg": 900}, guides), [])
        daily_ids = {
            guide.id for guide in retrieve_guides("DAILY_ACTION", {"is_hypertension_diagnosed": True}, guides)
        }
        self.assertIn("htn_less_salt", daily_ids)
