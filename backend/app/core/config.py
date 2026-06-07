from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi-Tenant Crypto Trading Platform"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")

    database_url: str = Field(
        default="postgresql+psycopg://trading:trading@postgres:5432/trading_dev"
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    jwt_secret_key: str = Field(default="change-me-in-local-env")
    jwt_expires_minutes: int = Field(default=60)
    secret_encryption_key: str = Field(default="change-me-32-byte-key")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
