
"""챌린지 DB 조회 (docs/api.md 8-9)."""

from app.models.challenge_checks import ChallengeCheck
from app.models.challenge_participants import (
    ChallengeParticipant,
    ParticipantStatus,
)
from app.models.challenges import Challenge

VISIBLE_STATUSES = (
    ParticipantStatus.INVITED,
    ParticipantStatus.JOINED,
)


class ChallengeRepository:
    async def list_for_user(
        self,
        user_id: int,
        status: str | None = None,
    ) -> list[Challenge]:
        """내가 초대받았거나 참여 중인 챌린지 조회."""
        memberships = await ChallengeParticipant.filter(
            user_id=user_id,
            status__in=VISIBLE_STATUSES,
        )

        challenge_ids = [item.challenge_id for item in memberships]
        if not challenge_ids:
            return []

        query = Challenge.filter(id__in=challenge_ids)

        if status is not None:
            query = query.filter(status=status)

        return await query.order_by("-created_at", "-id")

    async def get_for_user(
        self,
        challenge_id: int,
        user_id: int,
    ):
        """접근 권한이 있는 챌린지만 반환."""
        membership = await ChallengeParticipant.get_or_none(
            challenge_id=challenge_id,
            user_id=user_id,
            status__in=VISIBLE_STATUSES,
        )

        if membership is None:
            return None

        challenge = await Challenge.get_or_none(id=challenge_id)
        if challenge is None:
            return None

        return challenge, membership

    async def get_participants(self, challenge_id: int):
        return await ChallengeParticipant.filter(
            challenge_id=challenge_id,
        ).prefetch_related("user").order_by("id")

    async def get_my_checks(
        self,
        challenge_id: int,
        user_id: int,
    ):
        return await ChallengeCheck.filter(
            challenge_id=challenge_id,
            user_id=user_id,
        ).order_by("checked_on")
