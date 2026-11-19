import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # 기본값은 로컬 기준("localhost", 6379)으로 두고,
    # .env나 Docker Compose 환경변수에 REDIS_HOST="redis"가 있으면 자동으로 덮어씀
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
