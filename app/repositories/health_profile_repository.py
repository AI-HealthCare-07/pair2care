from typing import Any

from tortoise import BaseDBAsyncClient

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
