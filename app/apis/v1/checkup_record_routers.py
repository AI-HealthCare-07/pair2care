"""4장 검진 수치 API (S-07)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import ORJSONResponse

from app.dependencies.security import get_request_user
from app.dtos.checkup_records import CheckupRecordCreateRequest, CheckupRecordUpdateRequest
from app.models.users import User
from app.services.checkup_records import DEFAULT_LIMIT, MAX_LIMIT, CheckupRecordService

checkup_record_router = APIRouter(prefix="/checkup-records", tags=["checkup-records"])


@checkup_record_router.post("", status_code=status.HTTP_201_CREATED)
async def create_checkup_record(
    data: CheckupRecordCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[CheckupRecordService, Depends(CheckupRecordService)],
) -> ORJSONResponse:
    """4-1 저장 → 최근 설문으로 다시 예측."""
    return ORJSONResponse(await service.create(user, data), status_code=status.HTTP_201_CREATED)


@checkup_record_router.get("")
async def list_checkup_records(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[CheckupRecordService, Depends(CheckupRecordService)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    """4-2 목록 (검진 날짜 최신순)."""
    return await service.list_records(user, limit, cursor)


@checkup_record_router.get("/{record_id}")
async def get_checkup_record(
    record_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[CheckupRecordService, Depends(CheckupRecordService)],
) -> dict[str, Any]:
    """4-3 한 건."""
    return await service.get(user, record_id)


@checkup_record_router.patch("/{record_id}")
async def update_checkup_record(
    record_id: int,
    data: CheckupRecordUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[CheckupRecordService, Depends(CheckupRecordService)],
) -> dict[str, Any]:
    """4-4 수정 (보낸 필드만)."""
    return await service.update(user, record_id, data)


@checkup_record_router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checkup_record(
    record_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[CheckupRecordService, Depends(CheckupRecordService)],
) -> Response:
    """4-5 삭제."""
    await service.delete(user, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
