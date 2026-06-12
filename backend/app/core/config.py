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

    testnet_adapters_enabled: bool = Field(default=False)
    binance_testnet_rest_base_url: str = Field(default="https://testnet.binance.vision")
    bybit_testnet_rest_base_url: str = Field(default="https://api-testnet.bybit.com")
    okx_demo_rest_base_url: str = Field(default="https://openapi.okx.com")

    telegram_alerts_enabled: bool = Field(default=False)
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    email_alerts_enabled: bool = Field(default=False)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    alert_email_from: str = Field(default="")
    alert_email_to: str = Field(default="")
    webhook_alerts_enabled: bool = Field(default=False)
    alert_webhook_url: str = Field(default="")
    alert_webhook_secret: str = Field(default="")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
