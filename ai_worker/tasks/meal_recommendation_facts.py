"""식단 18종의 모델 라벨을 기준으로 국물 음식 여부를 판별한다."""

# docs/erd.md의 고정 18종. 간장게장과 볶음·조림에 가까운 닭볶음탕은 제외한다.
BROTH_MODEL_LABELS = frozenset(
    {
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
    }
)


NON_BROTH_MODEL_LABELS = frozenset({"간장게장", "닭볶음탕"})


def is_non_broth_model_label(label: str | None) -> bool:
    return label in NON_BROTH_MODEL_LABELS


def is_broth_model_label(label: str | None) -> bool:
    return label in BROTH_MODEL_LABELS
