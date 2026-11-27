"""챌린지 DB 조회 (docs/api.md 8-9)."""

from datetime import date, datetime, timedelta

from tortoise.transactions import in_transaction

from app.models.challenge_checks import ChallengeCheck
from app.models.challenge_participants import (
    ChallengeParticipant,
    ParticipantStatus,
)
from app.models.challenges import Challenge, ChallengeStatus

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
        return (
            await ChallengeParticipant.filter(
                challenge_id=challenge_id,
            )
            .prefetch_related("user")
            .order_by("id")
        )

    async def get_my_checks(
        self,
        challenge_id: int,
        user_id: int,
    ):
        return await ChallengeCheck.filter(
            challenge_id=challenge_id,
            user_id=user_id,
        ).order_by("checked_on")

    async def create_solo(
        self,
        *,
        user_id: int,
        template_id: int | None,
        title: str,
        times_per_week: int,
        starts_on: date,
        ends_on: date | None,
        joined_at: datetime,
    ) -> Challenge:
        """챌린지와 참여자를 하나의 트랜잭션으로 생성한다."""

        async with in_transaction() as conn:
            challenge = await Challenge.create(
                created_by_id=user_id,
                challenge_template_id=template_id,
                pair_id=None,
                title=title,
                times_per_week=times_per_week,
                starts_on=starts_on,
                ends_on=ends_on,
                status=ChallengeStatus.ACTIVE,
                using_db=conn,
            )

            await ChallengeParticipant.create(
                challenge_id=challenge.id,
                user_id=user_id,
                status=ParticipantStatus.JOINED,
                joined_at=joined_at,
                using_db=conn,
            )

        return challenge

    async def get_or_create_check(
        self,
        challenge_id: int,
        user_id: int,
        checked_on: date,
    ) -> tuple[ChallengeCheck, bool]:
        """완료 체크를 생성하고, 이미 있으면 기존 기록을 반환한다."""
        return await ChallengeCheck.get_or_create(
            challenge_id=challenge_id,
            user_id=user_id,
            checked_on=checked_on,
        )

    async def count_checks_for_week(
        self,
        challenge_id: int,
        user_id: int,
        week_start: date,
    ) -> int:
        """해당 주의 완료 체크 횟수를 조회한다."""
        return await ChallengeCheck.filter(
            challenge_id=challenge_id,
            user_id=user_id,
            checked_on__gte=week_start,
            checked_on__lt=week_start + timedelta(days=7),
        ).count()

    async def delete_check(
        self,
        challenge_id: int,
        user_id: int,
        checked_on: date,
    ) -> int:
        """특정 날짜의 완료 체크 기록을 삭제한다."""
        return await ChallengeCheck.filter(
            challenge_id=challenge_id,
            user_id=user_id,
            checked_on=checked_on,
        ).delete()
