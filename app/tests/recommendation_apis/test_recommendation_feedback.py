"""11-9 추천 피드백과 11-2·11-4 my_feedback (REQ-NFR-019)."""

from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.recommendation_feedbacks import RecommendationFeedback
from app.models.recommendations import GenerationStatus, Recommendation, RecommendationType
from app.models.users import User
from app.tests.factories import make_signup_data

SOURCES = [{"number": 1, "guide_id": "prevention_walk", "title": "신체활동 가이드", "url": "https://example.com"}]


def feedback_url(rec_id: int) -> str:
    return f"/api/v1/recommendations/{rec_id}/feedback"


async def signup(client: AsyncClient, email: str) -> tuple[int, dict[str, str]]:
    response = await client.post("/api/v1/auth/signup", json=make_signup_data(email))
    assert response.status_code == status.HTTP_201_CREATED
    user = await User.get(email=email)
    return user.id, {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_rec(user_id: int, **overrides) -> Recommendation:
    data = {
        "user_id": user_id,
        "rec_type": RecommendationType.DAILY_ACTION,
        "target_on": date(2026, 11, 27),
        "status": GenerationStatus.COMPLETED,
        "content": "오늘 잠깐 걸어 보는 건 어때요? [1]",
        "sources": SOURCES,
    }
    data.update(overrides)
    return await Recommendation.create(**data)


class TestRecommendationFeedback(TestCase):
    async def test_save_then_overwrite_clears_reason(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, headers = await signup(client, "fb_save@example.com")
            rec = await make_rec(user_id)
            first = await client.put(
                feedback_url(rec.id), json={"is_helpful": False, "reason": "NOT_FIT"}, headers=headers
            )
            second = await client.put(feedback_url(rec.id), json={"is_helpful": True}, headers=headers)
        assert first.status_code == status.HTTP_200_OK
        assert first.json()["reason"] == "NOT_FIT"
        assert second.json() == {**second.json(), "recommendation_id": rec.id, "is_helpful": True, "reason": None}
        rows = await RecommendationFeedback.filter(recommendation_id=rec.id)
        assert len(rows) == 1  # 추천당 1행, 덮어씀
        assert rows[0].reason is None  # 도움 돼요로 바꾸면 이유 지움

    async def test_not_helpful_without_reason_is_ok(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, headers = await signup(client, "fb_noreason@example.com")
            rec = await make_rec(user_id)
            response = await client.put(feedback_url(rec.id), json={"is_helpful": False}, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["reason"] is None

    async def test_helpful_with_reason_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, headers = await signup(client, "fb_422@example.com")
            rec = await make_rec(user_id)
            response = await client.put(
                feedback_url(rec.id), json={"is_helpful": True, "reason": "OTHER"}, headers=headers
            )
            unknown = await client.put(
                feedback_url(rec.id), json={"is_helpful": False, "reason": "BAD"}, headers=headers
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert unknown.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_check_order(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_id, _ = await signup(client, "fb_owner@example.com")
            user_id, headers = await signup(client, "fb_other@example.com")
            others = await make_rec(owner_id)
            meal = await make_rec(user_id, rec_type=RecommendationType.MEAL_ALTERNATIVE, meal_id=1)
            pending = await make_rec(
                user_id, target_on=date(2026, 11, 26), status=GenerationStatus.PENDING, sources=None
            )
            no_evidence = await make_rec(user_id, target_on=date(2026, 11, 25), sources=[])
            body = {"is_helpful": True}
            missing = await client.put(feedback_url(999999), json=body, headers=headers)
            not_mine = await client.put(feedback_url(others.id), json=body, headers=headers)
            wrong_type = await client.put(feedback_url(meal.id), json=body, headers=headers)
            not_ready = await client.put(feedback_url(pending.id), json=body, headers=headers)
            empty = await client.put(feedback_url(no_evidence.id), json=body, headers=headers)
        assert missing.status_code == not_mine.status_code == status.HTTP_404_NOT_FOUND
        assert not_mine.json()["detail"] == "추천을 찾을 수 없어요."
        assert wrong_type.status_code == status.HTTP_400_BAD_REQUEST
        assert not_ready.status_code == status.HTTP_409_CONFLICT
        assert not_ready.json()["detail"] == "추천이 준비된 뒤에 남길 수 있어요."
        assert empty.status_code == status.HTTP_409_CONFLICT
        assert empty.json()["detail"] == "남길 추천이 없어요."
        assert await RecommendationFeedback.all().count() == 0

    async def test_daily_get_shows_my_feedback(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, headers = await signup(client, "fb_get@example.com")
            rec = await make_rec(user_id)
            params = {"target_on": "2026-11-27"}
            before = await client.get("/api/v1/recommendations/daily", params=params, headers=headers)
            await client.put(feedback_url(rec.id), json={"is_helpful": False, "reason": "TOO_HARD"}, headers=headers)
            after = await client.get("/api/v1/recommendations/daily", params=params, headers=headers)
        assert before.json()["my_feedback"] is None
        assert after.json()["my_feedback"] == {"is_helpful": False, "reason": "TOO_HARD"}

    async def test_requires_login(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(feedback_url(1), json={"is_helpful": True})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
