from app.dtos.auth import ConsentItem
from app.models.user_consents import UserConsent


class UserConsentRepository:
    def __init__(self):
        self._model = UserConsent

    async def create_many(self, user_id: int, consents: list[ConsentItem]) -> None:
        await self._model.bulk_create(
            [
                self._model(user_id=user_id, agreement=c.agreement, version=c.version, is_agreed=c.is_agreed)
                for c in consents
            ]
        )

    async def latest_by_agreement(self, user_id: int) -> dict[str, UserConsent]:
        """종류별 최신 행 (현재 동의 상태, api.md 2-6). 행이 쌓이는 구조라 id가 클수록 나중."""
        rows = await self._model.filter(user_id=user_id).order_by("id")
        return {row.agreement: row for row in rows}  # 같은 종류는 뒤 행이 덮어씀

    async def create(self, user_id: int, consent: ConsentItem) -> UserConsent:
        return await self._model.create(
            user_id=user_id, agreement=consent.agreement, version=consent.version, is_agreed=consent.is_agreed
        )
