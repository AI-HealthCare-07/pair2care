from typing import Any

from app.core import config

DEFAULT_PASSWORD = "Pair2care!"


def make_consents(*, is_agreed: bool = True, version: str | None = None) -> list[dict[str, Any]]:
    """가입에 필요한 약관 3종 동의 (api.md 2-1)"""
    return [
        {"agreement": agreement, "version": version or config.TERMS_VERSION, "is_agreed": is_agreed}
        for agreement in ("TERMS", "PRIVACY", "SENSITIVE_HEALTH")
    ]


def make_signup_data(email: str, **overrides: Any) -> dict[str, Any]:
    """회원가입 요청 본문. 바꾸고 싶은 필드만 overrides로 넘김"""
    data: dict[str, Any] = {
        "email": email,
        "password": DEFAULT_PASSWORD,
        "nickname": "테스터",
        "gender": "MALE",
        "birthday": "1990-01-01",
        "consents": make_consents(),
    }
    data.update(overrides)
    return data
