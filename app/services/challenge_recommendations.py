"""Select a supported, unfinished challenge from the signed-in user's records."""

from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import BaseModel
from tortoise.exceptions import OperationalError

from app.core import config
from app.models.users import User

WALK_SOURCE = "질병관리청 국가건강정보포털 - 고혈압"
WALK_URL = (
    "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/"
    "gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=6765"
)


class ChallengeRecommendation(BaseModel):
    challenge_id: int
    message: str
    source_title: str = WALK_SOURCE
    source_url: str = WALK_URL


async def _next_walking_challenge_id(user_id: int) -> int | None:
    today = datetime.now(config.TIMEZONE).date()
    week_start = today - timedelta(days=today.weekday())
    try:
        rows = await User._meta.db.execute_query_dict(
            """
            SELECT challenge.id,
                   COALESCE(participant.times_per_week, challenge.times_per_week) - COUNT(record.id) AS remaining
            FROM challenge_participants AS participant
            JOIN challenges AS challenge ON challenge.id = participant.challenge_id
            JOIN challenge_templates AS template ON template.id = challenge.challenge_template_id
            LEFT JOIN challenge_checks AS record ON record.challenge_id = challenge.id
                AND record.user_id = participant.user_id AND record.checked_on BETWEEN %s AND %s
            WHERE participant.user_id = %s AND participant.status = 'JOINED'
                AND challenge.status = 'ACTIVE' AND template.category = 'WALK'
                AND challenge.starts_on <= %s AND (challenge.ends_on IS NULL OR challenge.ends_on >= %s)
            GROUP BY challenge.id, participant.times_per_week, challenge.times_per_week
            HAVING remaining > 0 AND COUNT(CASE WHEN record.checked_on = %s THEN 1 END) = 0
            ORDER BY remaining, challenge.id
            LIMIT 1
            """,
            [week_start, today, user_id, today, today, today],
        )
    except OperationalError as exc:
        if exc.args and getattr(exc.args[0], "args", ())[:1] == (1146,):
            raise HTTPException(503, "챌린지 기록을 아직 불러올 수 없어요.") from exc
        raise
    return int(rows[0]["id"]) if rows else None


async def recommend_challenge(user_id: int) -> ChallengeRecommendation | None:
    selected_id = await _next_walking_challenge_id(user_id)
    if selected_id is None:
        return None
    return ChallengeRecommendation(challenge_id=selected_id, message="오늘 남아 있는 걷기 챌린지를 해볼까요?")
