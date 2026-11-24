"""3-6 설문 문항 정의 API (api.md 3-6)."""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.health_profiles import HealthProfile, SurveyKind
from app.models.users import Gender, User
from app.services.survey.validation import resolve_answers
from app.tests.factories import DEFAULT_PASSWORD, make_signup_data
from app.tests.survey.test_validation import make_answers

QUESTIONS_URL = "/api/v1/health-profiles/questions"


class TestSurveyQuestionsAPI(TestCase):
    async def login(self, client: AsyncClient, email: str) -> None:
        await client.post("/api/v1/auth/signup", json=make_signup_data(email))
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    async def save_onboarding(self, email: str) -> None:
        # 3-1이 붙기 전이라 검사·채우기 결과를 바로 저장 (술 마심 → 13번 해당, 비흡연 → 16번 888)
        user = await User.get(email=email)
        values = resolve_answers(SurveyKind.ONBOARDING, Gender.MALE, make_answers())
        await HealthProfile.create(user=user, kind=SurveyKind.ONBOARDING, survey_version="v1.0", **values)

    async def test_onboarding_without_profile_is_200(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await self.login(client, "q-onboarding@example.com")
            response = await client.get(QUESTIONS_URL, params={"kind": "ONBOARDING"})

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["survey_version"] == "v1.0"
        assert len(body["questions"]) == 21

    async def test_weekly_without_onboarding_is_409(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await self.login(client, "q-weekly-409@example.com")
            response = await client.get(QUESTIONS_URL, params={"kind": "WEEKLY"})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {"detail": "가입 설문을 먼저 해 주세요.", "code": "ONBOARDING_REQUIRED"}

    async def test_weekly_uses_latest_profile(self) -> None:
        email = "q-weekly@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await self.login(client, email)
            await self.save_onboarding(email)
            response = await client.get(QUESTIONS_URL, params={"kind": "WEEKLY"})

        assert response.status_code == status.HTTP_200_OK
        flags = {q["field"]: q.get("ask_when_applicable") for q in response.json()["questions"]}
        assert len(flags) == 12
        assert flags["binge_frequency"] is False  # 직전에 해당(2) → 다시 안 물음
        assert flags["cigarettes_per_day"] is True  # 직전에 비해당(888) → 해당되면 물음

    async def test_invalid_kind_is_422(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await self.login(client, "q-invalid@example.com")
            response = await client.get(QUESTIONS_URL, params={"kind": "DAILY"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_requires_login(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(QUESTIONS_URL, params={"kind": "ONBOARDING"})

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
