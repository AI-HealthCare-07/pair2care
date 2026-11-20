import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # 기본값은 로컬 기준("localhost", 6379)으로 두고,
    # .env나 Docker Compose 환경변수에 REDIS_HOST="redis"가 있으면 자동으로 덮어씀
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # 워커 이름(Consumer 이름). 비워 두면 호스트명을 씀 → 워커가 여러 대여도 이름이 겹치지 않음
    WORKER_NAME: str = ""

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
