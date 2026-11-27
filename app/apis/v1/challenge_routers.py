"""챌린지 API (docs/api.md 8장)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.dtos.challenges import ChallengeCheckRequest, ChallengeCreateRequest
from app.models.challenges import ChallengeStatus
from app.models.users import User
from app.services.challenges import ChallengeService

challenge_router = APIRouter(
    prefix="/challenges",
    tags=["challenges"],
)


@challenge_router.post("", status_code=status.HTTP_201_CREATED)
async def create_challenge(
    data: ChallengeCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> dict[str, Any]:
    """8-7. SOLO 챌린지 생성."""
    return await service.create(user, data)


@challenge_router.get("")
async def list_challenges(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    status: ChallengeStatus | None = None,
) -> dict[str, Any]:
    """8-9. 내 챌린지 목록 조회."""
    return await service.list_challenges(user, status)


@challenge_router.get("/{challenge_id}")
async def get_challenge_detail(
    challenge_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> dict[str, Any]:
    """8-9. 챌린지 상세 조회."""
    return await service.get_detail(user, challenge_id)


@challenge_router.post("/{challenge_id}/checks")
async def check_challenge(
    challenge_id: int,
    data: ChallengeCheckRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> ORJSONResponse:
    """8-10. 챌린지 완료 체크."""
    body, created = await service.check(
        user,
        challenge_id,
        data.checked_on,
    )

    return ORJSONResponse(
        content=body,
        status_code=(status.HTTP_201_CREATED if created else status.HTTP_200_OK),
    )


@challenge_router.delete(
    "/{challenge_id}/checks/{checked_on}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def uncheck_challenge(
    challenge_id: int,
    checked_on: date,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    """8-10. 완료 체크 취소."""
    await service.uncheck(user, challenge_id, checked_on)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
