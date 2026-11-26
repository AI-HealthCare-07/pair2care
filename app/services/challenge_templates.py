
"""8-1 챌린지 템플릿 조회 서비스."""

from typing import Any

from app.repositories.challenge_template_repository import (
    ChallengeTemplateRepository,
)


class ChallengeTemplateService:
    def __init__(self) -> None:
        self.repo = ChallengeTemplateRepository()

    async def list_templates(self) -> dict[str, Any]:
        """기본 챌린지 템플릿 목록을 반환한다."""
        items = await self.repo.list_all()
        return {"items": items}
