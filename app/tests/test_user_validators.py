# app/tests/test_user_validators.py
# 만 14세 경계: 생일 당일부터 가입 가능, 2/29생은 평년엔 3/1부터

from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.core.validators import user_validators
from app.core.validators.user_validators import validate_birthday


def fixed_today(today: date) -> type[datetime]:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return datetime(today.year, today.month, today.day, tzinfo=tz)

    return FixedDatetime


@pytest.mark.parametrize(
    ("today", "birthday", "is_allowed"),
    [
        (date(2026, 11, 26), date(2012, 11, 26), True),  # 14번째 생일 당일
        (date(2026, 11, 26), date(2012, 11, 27), False),  # 생일 하루 전
        (date(2026, 11, 26), date(2012, 11, 25), True),
        (date(2026, 2, 28), date(2012, 2, 29), False),  # 평년 2/28은 아직 만 13세
        (date(2026, 3, 1), date(2012, 2, 29), True),
    ],
)
def test_validate_birthday_14_boundary(today: date, birthday: date, is_allowed: bool) -> None:
    with patch.object(user_validators, "datetime", fixed_today(today)):
        if is_allowed:
            assert validate_birthday(birthday) == birthday
        else:
            with pytest.raises(ValueError):
                validate_birthday(birthday)
