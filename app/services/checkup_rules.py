"""4-1·4-4 검진 수치 규칙 (DB 없이 쓰는 순수 함수). 위반이면 400."""

from collections.abc import Mapping
from datetime import date
from typing import Any, Final

from fastapi import HTTPException, status

CHECKUP_VALUE_FIELDS: Final = (
    "systolic_bp",
    "diastolic_bp",
    "fasting_glucose",
    "waist_cm",
    "triglyceride",
    "hdl_cholesterol",
    "hba1c",
)

FUTURE_DATE_DETAIL: Final = "검진 날짜는 오늘 이후로 입력할 수 없어요."
MISSING_DATE_DETAIL: Final = "검진 날짜를 입력해 주세요."
BLOOD_PRESSURE_DETAIL: Final = "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."
NO_VALUE_DETAIL: Final = "검진 수치를 하나 이상 입력해 주세요."


def check_checkup_values(values: Mapping[str, Any], today: date) -> None:
    """저장될 값 전체(수정이면 기존 값과 합친 뒤)를 검사. 날짜 → 혈압 → 최소 1개 순서, 첫 위반 하나만."""
    checked_on = values.get("checked_on")
    if checked_on is None:
        raise bad_request(MISSING_DATE_DETAIL)
    if checked_on > today:
        raise bad_request(FUTURE_DATE_DETAIL)

    systolic, diastolic = values.get("systolic_bp"), values.get("diastolic_bp")
    if systolic is not None and diastolic is not None and systolic <= diastolic:
        raise bad_request(BLOOD_PRESSURE_DETAIL)

    if all(values.get(field) is None for field in CHECKUP_VALUE_FIELDS):
        raise bad_request(NO_VALUE_DETAIL)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
