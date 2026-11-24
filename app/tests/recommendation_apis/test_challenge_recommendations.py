from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.dependencies.security import get_request_user
from app.main import app
from app.models.users import User
from app.services import challenge_recommendations as service


async def test_returns_candidate_without_calling_claude_when_only_one() -> None:
    with (
        patch.object(service, "_walking_candidates", AsyncMock(return_value=[(31, 1)])),
        patch.object(service, "_select_with_claude", AsyncMock()) as select,
    ):
        result = await service.recommend_challenge(4)
    assert result is not None and result.challenge_id == 31
    select.assert_not_awaited()


async def test_claude_uses_temporary_ids_and_rechecks_candidate(monkeypatch) -> None:
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"content": [{"type": "text", "text": '{"selected_id":"2"}'}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    with (
        patch.object(service.httpx, "AsyncClient", return_value=client),
        patch.object(service, "_walking_candidates", AsyncMock(side_effect=[[(31, 1), (32, 2)], [(31, 1)]])),
    ):
        result = await service.recommend_challenge(4)
    assert result is not None and result.challenge_id == 31
    assert b"31" not in sent[0].content and b"32" not in sent[0].content


def test_authenticated_endpoint_returns_no_candidate() -> None:
    path = "/api/v1/recommendations/challenges/next"
    client = TestClient(app)
    assert client.get(path).status_code == 401
    app.dependency_overrides[get_request_user] = lambda: User(id=4)
    try:
        with patch.object(service, "_walking_candidates", AsyncMock(return_value=[])) as candidates:
            response = client.get(path)
        assert response.status_code == 200
        assert response.json() is None
        assert response.headers["Cache-Control"] == "no-store"
        candidates.assert_awaited_once_with(4)
    finally:
        del app.dependency_overrides[get_request_user]
