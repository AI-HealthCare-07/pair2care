"""2-1 선택 동의 MODEL_IMPROVEMENT, 2-6 동의 조회·재동의·켜기/끄기."""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.main import app
from app.models.user_consents import UserConsent
from app.tests.factories import make_consents, make_signup_data

URL = "/api/v1/users/me/consents"


def model_improvement(is_agreed: bool, version: str | None = None) -> dict:
    return {"agreement": "MODEL_IMPROVEMENT", "version": version or config.TERMS_VERSION, "is_agreed": is_agreed}


async def signup(client: AsyncClient, email: str, consents: list[dict] | None = None) -> dict[str, str]:
    data = make_signup_data(email, consents=consents or make_consents())
    response = await client.post("/api/v1/auth/signup", json=data)
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestConsentApis(TestCase):
    async def test_signup_without_model_improvement_lists_it_unanswered(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "consent_none@example.com")
            response = await client.get(URL, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert [i["agreement"] for i in body["items"]] == ["TERMS", "PRIVACY", "SENSITIVE_HEALTH", "MODEL_IMPROVEMENT"]
        assert body["items"][3] == {
            "agreement": "MODEL_IMPROVEMENT",
            "version": None,
            "is_agreed": False,
            "agreed_at": None,
            "current_version": config.TERMS_VERSION,
        }
        assert body["needs_reconsent"] is False

    async def test_signup_with_model_improvement_saved(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "consent_yes@example.com", make_consents() + [model_improvement(True)])
            response = await client.get(URL, headers=headers)
        item = response.json()["items"][3]
        assert item["is_agreed"] is True
        assert item["agreed_at"] is not None

    async def test_signup_duplicate_agreement_422(self):
        consents = make_consents() + [model_improvement(True), model_improvement(False)]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/signup", json=make_signup_data("dup@example.com", consents=consents)
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_signup_optional_old_version_400(self):
        consents = make_consents() + [model_improvement(True, version="v0.9")]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/signup", json=make_signup_data("oldopt@example.com", consents=consents)
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "SIGNUP_TERMS_REQUIRED"

    async def test_toggle_model_improvement_stacks_rows(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "toggle@example.com")
            on = await client.post(URL, json=model_improvement(True), headers=headers)
            off = await client.post(URL, json=model_improvement(False), headers=headers)
            listed = await client.get(URL, headers=headers)
        assert on.status_code == off.status_code == status.HTTP_201_CREATED
        assert on.json()["is_agreed"] is True
        assert off.json()["is_agreed"] is False
        assert listed.json()["items"][3]["is_agreed"] is False
        # 철회도 새 행으로 쌓임 (재학습은 뽑을 때 최신 행을 봄, docs/feedback-loop.md ①)
        assert await UserConsent.filter(agreement="MODEL_IMPROVEMENT").count() == 2

    async def test_required_withdraw_400(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "withdraw@example.com")
            body = {"agreement": "PRIVACY", "version": config.TERMS_VERSION, "is_agreed": False}
            response = await client.post(URL, json=body, headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "필수 동의는 철회할 수 없어요. 탈퇴로 진행해 주세요."

    async def test_old_version_400(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "oldver@example.com")
            response = await client.post(URL, json=model_improvement(True, version="v0.9"), headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_needs_reconsent_when_required_is_old(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await signup(client, "reconsent@example.com")
            await UserConsent.filter(agreement="PRIVACY").update(version="v0.9")
            before = await client.get(URL, headers=headers)
            await client.post(
                URL, json={"agreement": "PRIVACY", "version": config.TERMS_VERSION, "is_agreed": True}, headers=headers
            )
            after = await client.get(URL, headers=headers)
        assert before.json()["needs_reconsent"] is True
        assert after.json()["needs_reconsent"] is False

    async def test_requires_login(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
