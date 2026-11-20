import re
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from app.core import config

SPECIAL_CHARS = r"!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~"  # string.punctuation과 같은 32자


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 해요.")

    # 영문·숫자·키보드 기호 말고 다른 문자(공백·한글 등)는 안 됨
    if not re.fullmatch(f"[A-Za-z0-9{SPECIAL_CHARS}]+", password):
        raise ValueError("비밀번호에는 영문, 숫자, 특수문자만 쓸 수 있어요.")

    # 영문·숫자·특수문자가 각각 하나 이상 있어야 함
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("영문, 숫자, 특수문자를 모두 넣어 주세요.")
    if not re.search(r"[0-9]", password):
        raise ValueError("영문, 숫자, 특수문자를 모두 넣어 주세요.")
    if not re.search(f"[{SPECIAL_CHARS}]", password):
        raise ValueError("영문, 숫자, 특수문자를 모두 넣어 주세요.")

    return password


def validate_birthday(birthday: date | str) -> date:
    if isinstance(birthday, str):
        try:
            birthday = date.fromisoformat(birthday)
        except ValueError as e:
            raise ValueError("올바르지 않은 날짜 형식입니다. format: YYYY-MM-DD") from e

    is_over_14 = birthday < datetime.now(tz=config.TIMEZONE).date() - relativedelta(years=14)
    if not is_over_14:
        raise ValueError("서비스 약관에 따라 만14세 미만은 회원가입이 불가합니다.")

    return birthday
