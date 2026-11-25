"""4-1·4-4 검진 수치 규칙 (DB 없이 도는 순수 테스트)."""

from datetime import date
from typing import Any

import pytest
from fastapi import HTTPException

from app.services.checkup_rules import check_checkup_values

TODAY = date(2026, 11, 25)


def values(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"checked_on": date(2026, 5, 10), "systolic_bp": 134, "diastolic_bp": 86}
    data.update(overrides)
    return data


def test_valid_values_pass() -> None:
    check_checkup_values(values(), TODAY)
    check_checkup_values(values(checked_on=TODAY), TODAY)  # 오늘은 됨
    check_checkup_values({"checked_on": TODAY, "hba1c": 5.8}, TODAY)  # 수치 하나만 있어도 됨


@pytest.mark.parametrize(
    ("data", "detail"),
    [
        (values(checked_on=date(2026, 11, 26)), "검진 날짜는 오늘 이후로 입력할 수 없어요."),
        (values(checked_on=None), "검진 날짜를 입력해 주세요."),
        (values(systolic_bp=86, diastolic_bp=86), "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."),
        (values(systolic_bp=80, diastolic_bp=90), "수축기 혈압(높은 값)이 이완기 혈압(낮은 값)보다 커야 해요."),
        ({"checked_on": TODAY}, "검진 수치를 하나 이상 입력해 주세요."),
        ({"checked_on": TODAY, "systolic_bp": None, "hba1c": None}, "검진 수치를 하나 이상 입력해 주세요."),
    ],
)
def test_rule_violations_are_400(data: dict[str, Any], detail: str) -> None:
    with pytest.raises(HTTPException) as exc:
        check_checkup_values(data, TODAY)

    assert exc.value.status_code == 400
    assert exc.value.detail == detail


def test_one_side_of_blood_pressure_is_ok() -> None:
    check_checkup_values(values(diastolic_bp=None), TODAY)


def test_first_violation_wins() -> None:
    # 날짜 → 혈압 → 최소 1개 순서
    with pytest.raises(HTTPException) as exc:
        check_checkup_values(values(checked_on=date(2027, 1, 1), systolic_bp=80, diastolic_bp=90), TODAY)
    assert "날짜" in str(exc.value.detail)
