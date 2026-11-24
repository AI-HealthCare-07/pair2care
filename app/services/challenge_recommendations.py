"""Select a supported, unfinished challenge from the signed-in user's records."""

import asyncio
import json
import os
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from tortoise.exceptions import OperationalError

from ai_worker.schemas.task import KST
from app.models.users import User

WALK_SOURCE = "질병관리청 국가건강정보포털 - 고혈압"
WALK_URL = (
    "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/"
    "gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=6765"
)
CLAUDE_LIMIT = asyncio.Semaphore(3)


class ChallengeRecommendation(BaseModel):
    challenge_id: int
    message: str
    source_title: str = WALK_SOURCE
    source_url: str = WALK_URL


async def _walking_candidates(user_id: int) -> list[tuple[int, int]]:
    today = datetime.now(KST).date()
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
            LIMIT 5
            """,
            [week_start, today, user_id, today, today, today],
        )
    except OperationalError as exc:
        if exc.args and getattr(exc.args[0], "args", ())[:1] == (1146,):
            raise HTTPException(503, "챌린지 기록을 아직 불러올 수 없어요.") from exc
        raise
    return [(int(row["id"]), int(row["remaining"])) for row in rows]


async def _select_with_claude(candidates: list[tuple[int, int]], key: str) -> int:
    # Model receives local labels and counts only. No account/challenge IDs or custom titles.
    choices = {str(index): remaining for index, (_, remaining) in enumerate(candidates, start=1)}
    async with asyncio.timeout(5), CLAUDE_LIMIT, httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={
                "model": os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"),
                "max_tokens": 80,
                "system": (
                    "Choose one existing walking challenge that is achievable today. "
                    "The input maps candidate IDs to their remaining weekly check-ins. "
                    'Return only JSON in the form {"selected_id":"1"}.'
                ),
                "messages": [{"role": "user", "content": json.dumps(choices)}],
            },
        )
        response.raise_for_status()
        text = "".join(block["text"] for block in response.json()["content"] if block["type"] == "text")
        label = json.loads(text)["selected_id"]
        if not isinstance(label, str) or label not in choices:
            raise ValueError("Invalid candidate ID")
        return candidates[int(label) - 1][0]


async def recommend_challenge(user_id: int) -> ChallengeRecommendation | None:
    candidates = await _walking_candidates(user_id)
    if not candidates:
        return None
    selected_id = candidates[0][0]
    key = os.getenv("ANTHROPIC_API_KEY")
    if key and len(candidates) > 1:
        try:
            selected_id = await _select_with_claude(candidates, key)
        except (TimeoutError, httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
        # Confirm the selected challenge is still pending after the external call.
        current = await _walking_candidates(user_id)
        if not current:
            return None
        if selected_id not in {challenge_id for challenge_id, _ in current}:
            selected_id = current[0][0]
    return ChallengeRecommendation(challenge_id=selected_id, message="오늘 남아 있는 걷기 챌린지를 해볼까요?")
