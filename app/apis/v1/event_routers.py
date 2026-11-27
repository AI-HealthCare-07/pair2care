"""12-6 공통 SSE. 라우터는 받고 넘기기만, 로직은 app/services/events.py."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.dependencies.security import get_request_user
from app.models.users import User
from app.services.events import event_stream, issue_ticket, use_ticket

event_router = APIRouter(prefix="/events", tags=["events"])

TICKET_INVALID_DETAIL = "연결이 만료됐어요. 다시 연결해 주세요."


@event_router.post("/ticket")
async def create_ticket(user: Annotated[User, Depends(get_request_user)]) -> dict:
    """로그인한 사람에게 30초짜리 1회용 티켓. EventSource 주소에 이걸 붙여 연결함."""
    return await issue_ticket(user.id)


@event_router.get("")
async def stream_events(ticket: Annotated[str | None, Query(max_length=100)] = None) -> StreamingResponse:
    """티켓으로 인증하고(헤더 없음) text/event-stream을 엶. 티켓이 없거나 만료·재사용이면 401 (빠져도 422가 아니라 401, 12-6)."""
    user_id = await use_ticket(ticket) if ticket else None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=TICKET_INVALID_DETAIL)
    return StreamingResponse(
        event_stream(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",  # 중간 캐시가 스트림을 붙잡지 않게
            "X-Accel-Buffering": "no",  # nginx가 모아 두지 말고 바로 넘기게 (설정의 proxy_buffering off와 같은 효과)
        },
    )
