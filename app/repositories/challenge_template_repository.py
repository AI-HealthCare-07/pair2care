
"""챌린지 템플릿 DB 조회 (api.md 8-1)."""

from typing import Any

from app.models.challenge_templates import ChallengeTemplate


class ChallengeTemplateRepository:
    async def list_all(self) -> list[dict[str, Any]]:
        """기본 챌린지 템플릿을 ID 순서로 조회한다."""
        return await (
            ChallengeTemplate.all()
            .order_by("id")
            .values(
                "id",
                "title",
                "category",
                "default_times_per_week",
            )
        )
