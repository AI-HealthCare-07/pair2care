
"""8-1 기본 챌린지 목록 API 테스트."""

from httpx import ASGITransport, AsyncClient
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge_templates import (
    ChallengeCategory,
    ChallengeTemplate,
)

URL = "/api/v1/challenge-templates"


class TestChallengeTemplatesAPI(TestCase):

    async def test_empty_list(self) -> None:
        """데이터가 없으면 빈 목록을 반환한다."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 200
        assert response.json() == {"items": []}

    async def test_list_seven_templates(self) -> None:
        """기본 챌린지 7종을 조회할 수 있다."""
        templates = [
            (ChallengeCategory.WALK, "10분 걷기", 3),
            (ChallengeCategory.WATER, "물 6잔 마시기", 5),
            (ChallengeCategory.EXERCISE, "30분 운동하기", 3),
            (ChallengeCategory.STRETCH, "5분 스트레칭", 5),
            (ChallengeCategory.LESS_ALCOHOL, "술 없는 날", 4),
            (ChallengeCategory.WEIGHT, "체중 재기", 2),
            (ChallengeCategory.NO_SMOKING, "금연", 7),
        ]

        for category, title, times in templates:
            await ChallengeTemplate.create(
                category=category,
                title=title,
                default_times_per_week=times,
            )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 200

        items = response.json()["items"]
        assert len(items) == 7

        assert [
            (
                item["category"],
                item["title"],
                item["default_times_per_week"],
            )
            for item in items
        ] == [
            (category.value, title, times)
            for category, title, times in templates
        ]
