"""기본 챌린지 템플릿 7종 초기 데이터 등록."""

import asyncio

from tortoise import Tortoise

from app.core.db.databases import TORTOISE_ORM
from app.models.challenge_templates import (
    ChallengeCategory,
    ChallengeTemplate,
)

# 팀장님·성은님 검토 내용 반영 (2026-11-26)
# (카테고리, 제목, 기본 주간 횟수)
DEFAULT_TEMPLATES = [
    (ChallengeCategory.WALK, "10분 걷기", 3),
    (ChallengeCategory.WATER, "물 6잔 마시기", 5),
    (ChallengeCategory.EXERCISE, "30분 운동하기", 3),
    (ChallengeCategory.STRETCH, "5분 스트레칭", 5),
    (ChallengeCategory.LESS_ALCOHOL, "술 없는 날", 4),
    (ChallengeCategory.WEIGHT, "체중 재기", 2),
    (ChallengeCategory.NO_SMOKING, "금연", 7),
]


async def seed_templates() -> None:
    """기본 챌린지 템플릿 7종을 등록한다."""
    for category, title, times_per_week in DEFAULT_TEMPLATES:
        existing = await ChallengeTemplate.filter(category=category).first()

        if existing is not None:
            print(f"이미 등록됨: {existing.title}")
            continue

        template = await ChallengeTemplate.create(
            title=title,
            category=category,
            default_times_per_week=times_per_week,
        )

        print(f"등록 완료: {template.title}")


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    try:
        await seed_templates()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
