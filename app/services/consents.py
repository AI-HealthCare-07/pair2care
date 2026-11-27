"""2-6 약관 동의 조회·재동의·선택 동의 켜기/끄기. 행을 쌓고 종류별 최신 행이 현재 상태."""

from fastapi import HTTPException
from starlette import status

from app.core import config
from app.dtos.auth import ConsentItem
from app.dtos.consents import ConsentListResponse, ConsentStatus
from app.models.user_consents import REQUIRED_AGREEMENTS, Agreement, UserConsent
from app.repositories.user_consent_repository import UserConsentRepository

REQUIRED_WITHDRAW_DETAIL = "필수 동의는 철회할 수 없어요. 탈퇴로 진행해 주세요."
VERSION_MISMATCH_DETAIL = "약관 버전이 바뀌었어요. 새로고침해 주세요."


class ConsentService:
    def __init__(self) -> None:
        self.repo = UserConsentRepository()

    async def get_consents(self, user_id: int) -> ConsentListResponse:
        latest = await self.repo.latest_by_agreement(user_id)
        items = [to_status(agreement, latest.get(agreement)) for agreement in Agreement]
        needs_reconsent = any(
            item.version != config.TERMS_VERSION for item in items if item.agreement in REQUIRED_AGREEMENTS
        )
        return ConsentListResponse(items=items, needs_reconsent=needs_reconsent)

    async def save_consent(self, user_id: int, consent: ConsentItem) -> ConsentStatus:
        if consent.agreement in REQUIRED_AGREEMENTS and not consent.is_agreed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, REQUIRED_WITHDRAW_DETAIL)
        if consent.version != config.TERMS_VERSION:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, VERSION_MISMATCH_DETAIL)
        row = await self.repo.create(user_id, consent)
        return to_status(consent.agreement, row)


def to_status(agreement: Agreement, row: UserConsent | None) -> ConsentStatus:
    if row is None:
        return ConsentStatus(
            agreement=agreement, version=None, is_agreed=False, agreed_at=None, current_version=config.TERMS_VERSION
        )
    return ConsentStatus(
        agreement=agreement,
        version=row.version,
        is_agreed=row.is_agreed,
        agreed_at=row.created_at,
        current_version=config.TERMS_VERSION,
    )
