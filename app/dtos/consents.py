from datetime import datetime

from pydantic import BaseModel

from app.models.user_consents import Agreement


class ConsentStatus(BaseModel):
    """2-6 종류별 현재 상태. 한 번도 답하지 않은 선택 동의는 version·agreed_at이 null"""

    agreement: Agreement
    version: str | None
    is_agreed: bool
    agreed_at: datetime | None
    current_version: str


class ConsentListResponse(BaseModel):
    items: list[ConsentStatus]
    needs_reconsent: bool  # 필수 3종 중 옛 버전이 있으면 true
