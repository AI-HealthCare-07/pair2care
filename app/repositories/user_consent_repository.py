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
