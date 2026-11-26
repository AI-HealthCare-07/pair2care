from typing import Any

from tortoise import BaseDBAsyncClient
from tortoise.expressions import Q

from app.models.health_profiles import HealthProfile, SurveyKind
from app.services.survey.questions import QUESTIONS


class HealthProfileRepository:
    def __init__(self) -> None:
        self._model = HealthProfile

    async def get_latest(self, user_id: int, using_db: BaseDBAsyncClient | None = None) -> HealthProfile | None:
        """내 최신 설문 행 (WEEKLY 직전 값 복사·ask_when_applicable 기준). 같은 시각이면 나중에 넣은 행."""
        query = self._model.filter(user_id=user_id).order_by("-created_at", "-id")
        if using_db is not None:
            query = query.using_db(using_db)
        return await query.first()

    async def get_for_user(self, user_id: int, profile_id: int) -> HealthProfile | None:
        """내 설문 한 건. 남의 것이면 None (있는지 드러내지 않게 404로)."""
        return await self._model.filter(id=profile_id, user_id=user_id).first()

    async def list_page(
        self, user_id: int, kind: SurveyKind | None, limit: int, cursor: HealthProfile | None
    ) -> list[HealthProfile]:
        """응답 시각 최신순, 같은 시각이면 나중에 넣은 것 먼저. cursor 행보다 뒤(오래된)부터."""
        query = self._model.filter(user_id=user_id)
        if kind is not None:
            query = query.filter(kind=kind)
        if cursor is not None:
            query = query.filter(
                Q(created_at__lt=cursor.created_at) | Q(created_at=cursor.created_at, id__lt=cursor.id)
            )
        return await query.order_by("-created_at", "-id").limit(limit)

    async def create(
        self,
        *,
        user_id: int,
        kind: SurveyKind,
        survey_version: str,
        values: dict[str, Any],
        using_db: BaseDBAsyncClient | None = None,
    ) -> HealthProfile:
        return await self._model.create(
            using_db=using_db, user_id=user_id, kind=kind, survey_version=survey_version, **values
        )


def to_answer_values(profile: HealthProfile) -> dict[str, Any]:
    """설문 행에서 문항 21개 값만 꺼냄 (검사·복사용 dict)."""
    return {question["field"]: getattr(profile, question["field"]) for question in QUESTIONS}
