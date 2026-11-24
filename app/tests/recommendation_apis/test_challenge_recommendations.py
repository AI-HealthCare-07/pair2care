from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

from fastapi.testclient import TestClient
from tortoise.exceptions import OperationalError

from app.dependencies.security import get_request_user
from app.main import app
from app.models.users import User
from app.services import challenge_recommendations as service


def test_authenticated_endpoint_returns_recommendation() -> None:
    app.dependency_overrides[get_request_user] = lambda: User(id=4)
    try:
        with patch.object(service, "_next_walking_challenge_id", AsyncMock(return_value=31)) as select:
            response = TestClient(app).get("/api/v1/recommendations/challenges/next")
        assert response.status_code == 200
        assert response.json()["challenge_id"] == 31
        assert response.json()["source_url"] == service.WALK_URL
        select.assert_awaited_once_with(4)
    finally:
        del app.dependency_overrides[get_request_user]


def test_authenticated_endpoint_returns_503_without_challenge_tables() -> None:
    app.dependency_overrides[get_request_user] = lambda: User(id=4)
    try:
        missing_table = OperationalError(Exception(1146, "Table does not exist"))
        db = SimpleNamespace(execute_query_dict=AsyncMock(side_effect=missing_table))
        with patch.object(type(User._meta), "db", new_callable=PropertyMock, return_value=db):
            response = TestClient(app).get("/api/v1/recommendations/challenges/next")
        assert response.status_code == 503
    finally:
        del app.dependency_overrides[get_request_user]


def test_authenticated_endpoint_returns_no_candidate() -> None:
    path = "/api/v1/recommendations/challenges/next"
    client = TestClient(app)
    assert client.get(path).status_code == 401
    app.dependency_overrides[get_request_user] = lambda: User(id=4)
    try:
        with patch.object(service, "_next_walking_challenge_id", AsyncMock(return_value=None)) as candidates:
            response = client.get(path)
        assert response.status_code == 200
        assert response.json() is None
        assert response.headers["Cache-Control"] == "no-store"
        candidates.assert_awaited_once_with(4)
    finally:
        del app.dependency_overrides[get_request_user]
