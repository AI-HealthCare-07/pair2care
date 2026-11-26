
"""8-1 기본 챌린지 템플릿 조회 API."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.services.challenge_templates import ChallengeTemplateService


challenge_template_router = APIRouter(
    prefix="/challenge-templates",
    tags=["challenge-templates"],
)


@challenge_template_router.get("")
async def list_challenge_templates(
    service: Annotated[
        ChallengeTemplateService,
        Depends(ChallengeTemplateService),
    ],
) -> dict[str, Any]:
    """기본 챌린지 템플릿 목록 조회."""
    return await service.list_templates()
