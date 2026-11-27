"""챌린지 서비스 (docs/api.md 8-7)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.dtos.challenges import ChallengeCreateRequest
from app.models.challenge_participants import ParticipantStatus
from app.models.challenges import ChallengeStatus
from app.models.users import User
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.challenge_template_repository import ChallengeTemplateRepository
from app.services.challenge_progress import week_progress

KST = ZoneInfo("Asia/Seoul")


class ChallengeService:
    async def create(self, user: User, data: ChallengeCreateRequest) -> dict:
        """8-7. SOLO 챌린지 생성."""

        # 1차 PR에서는 SOLO만 지원
        if data.mode != "SOLO" or data.invite_user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재는 혼자 하는 챌린지만 만들 수 있어요.",
            )

        now = datetime.now(KST)
        starts_on = data.starts_on or now.date()

        if starts_on < now.date():
            raise HTTPException(
                status_code=400,
                detail="시작 날짜는 오늘 이후로 선택해 주세요.",
            )

        if data.ends_on is not None and data.ends_on < starts_on:
            raise HTTPException(
                status_code=400,
                detail="종료 날짜는 시작 날짜보다 빠를 수 없어요.",
            )

        # 기본 챌린지 템플릿 확인
        template = None
        if data.challenge_template_id is not None:
            template = await ChallengeTemplateRepository().get_by_id(data.challenge_template_id)
            if template is None:
                raise HTTPException(
                    status_code=404,
                    detail="챌린지 템플릿을 찾을 수 없어요.",
                )

        title = data.title.strip() if data.title is not None else (template.title if template else None)

        if not title:
            raise HTTPException(
                status_code=400,
                detail="챌린지 제목을 입력해 주세요.",
            )

        # 챌린지와 참여자를 Repository에서 함께 생성
        challenge = await ChallengeRepository().create_solo(
            user_id=user.id,
            template_id=template.id if template else None,
            title=title,
            times_per_week=data.times_per_week,
            starts_on=starts_on,
            ends_on=data.ends_on,
            joined_at=now,
        )

        return {
            "id": challenge.id,
            "title": challenge.title,
            "mode": "SOLO",
            "times_per_week": challenge.times_per_week,
            "starts_on": challenge.starts_on,
            "ends_on": challenge.ends_on,
            "status": "ACTIVE",
            "participants": [
                {
                    "user_id": user.id,
                    "nickname": user.nickname,
                    "status": "JOINED",
                    "times_per_week": data.times_per_week,
                    "is_me": True,
                }
            ],
            "my_checks": [],
        }

    async def get_detail(self, user: User, challenge_id: int) -> dict:
        """8-9. 챌린지 상세 조회."""

        result = await ChallengeRepository().get_for_user(challenge_id, user.id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="챌린지를 찾을 수 없어요.",
            )

        challenge, membership = result
        repo = ChallengeRepository()

        participants = await repo.get_participants(challenge_id)
        checks = await repo.get_my_checks(challenge_id, user.id)

        active_count = sum(
            p.status
            in (
                ParticipantStatus.INVITED,
                ParticipantStatus.JOINED,
            )
            for p in participants
        )

        mode = "PAIR" if challenge.pair_id is not None else "GROUP" if active_count > 1 else "SOLO"

        return {
            "id": challenge.id,
            "title": challenge.title,
            "mode": mode,
            "times_per_week": challenge.times_per_week,
            "starts_on": challenge.starts_on.isoformat(),
            "ends_on": (challenge.ends_on.isoformat() if challenge.ends_on else None),
            "status": str(challenge.status),
            "participants": [
                {
                    "user_id": p.user_id,
                    "nickname": p.user.nickname,
                    "status": str(p.status),
                    "times_per_week": (p.times_per_week if p.times_per_week is not None else challenge.times_per_week),
                    "is_me": p.user_id == user.id,
                }
                for p in participants
            ],
            "my_checks": [check.checked_on.isoformat() for check in checks],
        }

    async def list_challenges(
        self,
        user: User,
        challenge_status: ChallengeStatus | None = None,
    ) -> dict:
        """8-9. 내가 참여하거나 초대받은 챌린지 목록."""

        repo = ChallengeRepository()
        challenges = await repo.list_for_user(
            user.id,
            challenge_status.value if challenge_status else None,
        )

        today = datetime.now(KST).date()
        week_start = today - timedelta(days=today.weekday())
        items = []

        for challenge in challenges:
            detail = await self.get_detail(user, challenge.id)

            me = next(p for p in detail["participants"] if p["is_me"])
            target = me["times_per_week"]

            checked_dates = [date.fromisoformat(value) for value in detail["my_checks"]]

            this_week_checked, _ = week_progress(
                checked_dates=checked_dates,
                week_start=week_start,
                target=target,
            )

            # 완료한 지난주부터 거슬러 올라가 연속 달성 주 계산
            streak = 0
            previous_week = week_start - timedelta(days=7)
            first_week = challenge.starts_on - timedelta(days=challenge.starts_on.weekday())

            while previous_week >= first_week:
                count = sum(previous_week <= day < previous_week + timedelta(days=7) for day in checked_dates)

                if count < target:
                    break

                streak += 1
                previous_week -= timedelta(days=7)

            items.append(
                {
                    "id": challenge.id,
                    "title": challenge.title,
                    "mode": detail["mode"],
                    "status": detail["status"],
                    "my_status": me["status"],
                    "my_times_per_week": target,
                    "this_week": {
                        "checked": this_week_checked,
                        "target": target,
                    },
                    "total_checked": len(checked_dates),
                    "streak_weeks": streak,
                    "checked_today": today in checked_dates,
                    "is_owner": challenge.created_by_id == user.id,
                    "decision_required": False,
                }
            )

        return {"items": items}

    async def check(
        self,
        user: User,
        challenge_id: int,
        checked_on: date | None = None,
    ) -> tuple[dict, bool]:
        """8-10. 완료 체크. 응답 데이터와 신규 생성 여부 반환."""

        today = datetime.now(KST).date()
        target_day = checked_on if checked_on is not None else today

        if target_day not in (today, today - timedelta(days=1)):
            raise HTTPException(
                status_code=400,
                detail="오늘 또는 어제 날짜만 체크할 수 있어요.",
            )

        result = await ChallengeRepository().get_for_user(challenge_id, user.id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="챌린지를 찾을 수 없어요.",
            )

        challenge, membership = result

        if membership.status != ParticipantStatus.JOINED:
            raise HTTPException(
                status_code=400,
                detail="참여 중인 챌린지만 체크할 수 있어요.",
            )

        if challenge.status != ChallengeStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="진행 중인 챌린지만 체크할 수 있어요.",
            )

        if target_day < challenge.starts_on or (challenge.ends_on is not None and target_day > challenge.ends_on):
            raise HTTPException(
                status_code=400,
                detail="챌린지 진행 기간이 아니에요.",
            )

        record, created = await ChallengeRepository().get_or_create_check(
            challenge_id=challenge_id,
            user_id=user.id,
            checked_on=target_day,
        )

        week_start = target_day - timedelta(days=target_day.weekday())
        count = await ChallengeRepository().count_checks_for_week(
            challenge_id=challenge_id,
            user_id=user.id,
            week_start=week_start,
        )

        return {
            "checked_on": record.checked_on.isoformat(),
            "this_week": {
                "checked": count,
                "target": (
                    membership.times_per_week if membership.times_per_week is not None else challenge.times_per_week
                ),
            },
        }, created

    async def uncheck(
        self,
        user: User,
        challenge_id: int,
        checked_on: date,
    ) -> None:
        """8-10. 오늘 또는 어제의 완료 체크 취소."""

        today = datetime.now(KST).date()

        if checked_on not in (today, today - timedelta(days=1)):
            raise HTTPException(
                status_code=400,
                detail="오늘 또는 어제 날짜만 취소할 수 있어요.",
            )

        result = await ChallengeRepository().get_for_user(challenge_id, user.id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="챌린지를 찾을 수 없어요.",
            )

        challenge, membership = result

        if membership.status != ParticipantStatus.JOINED:
            raise HTTPException(
                status_code=400,
                detail="참여 중인 챌린지만 체크를 취소할 수 있어요.",
            )

        if challenge.status != ChallengeStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="진행 중인 챌린지만 체크를 취소할 수 있어요.",
            )

        await ChallengeRepository().delete_check(
            challenge_id=challenge_id,
            user_id=user.id,
            checked_on=checked_on,
        )
