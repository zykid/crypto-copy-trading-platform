import dataclasses
from enum import StrEnum


class ExternalAlertChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclasses.dataclass(frozen=True)
class ExternalAlertConfig:
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_secret: str = ""


@dataclasses.dataclass(frozen=True)
class ExternalAlertPlan:
    enabled_channels: tuple[ExternalAlertChannel, ...]
    validation_errors: tuple[str, ...]
    redacted_summary: dict[str, str]

    @property
    def ready(self) -> bool:
        return bool(self.enabled_channels) and not self.validation_errors


def build_external_alert_plan(config: ExternalAlertConfig) -> ExternalAlertPlan:
    enabled_channels: list[ExternalAlertChannel] = []
    validation_errors: list[str] = []

    if config.telegram_enabled:
        enabled_channels.append(ExternalAlertChannel.TELEGRAM)
        _require(validation_errors, "telegram_bot_token", config.telegram_bot_token)
        _require(validation_errors, "telegram_chat_id", config.telegram_chat_id)

    if config.email_enabled:
        enabled_channels.append(ExternalAlertChannel.EMAIL)
        _require(validation_errors, "smtp_host", config.smtp_host)
        _require_positive_port(validation_errors, "smtp_port", config.smtp_port)
        _require(validation_errors, "smtp_username", config.smtp_username)
        _require(validation_errors, "smtp_password", config.smtp_password)
        _require(validation_errors, "alert_email_from", config.alert_email_from)
        _require(validation_errors, "alert_email_to", config.alert_email_to)

    if config.webhook_enabled:
        enabled_channels.append(ExternalAlertChannel.WEBHOOK)
        _require(validation_errors, "webhook_url", config.webhook_url)

    return ExternalAlertPlan(
        enabled_channels=tuple(enabled_channels),
        validation_errors=tuple(validation_errors),
        redacted_summary=_redacted_summary(config),
    )


def _require(errors: list[str], field_name: str, value: str) -> None:
    if not value:
        errors.append(f"{field_name} is required")


def _require_positive_port(errors: list[str], field_name: str, value: int) -> None:
    if value <= 0:
        errors.append(f"{field_name} must be positive")


def _redacted_summary(config: ExternalAlertConfig) -> dict[str, str]:
    return {
        "telegram_enabled": str(config.telegram_enabled),
        "telegram_bot_token": _redact(config.telegram_bot_token),
        "telegram_chat_id": _redact(config.telegram_chat_id),
        "email_enabled": str(config.email_enabled),
        "smtp_host": config.smtp_host,
        "smtp_port": str(config.smtp_port),
        "smtp_username": _redact(config.smtp_username),
        "smtp_password": _redact(config.smtp_password),
        "alert_email_from": _redact(config.alert_email_from),
        "alert_email_to": _redact(config.alert_email_to),
        "webhook_enabled": str(config.webhook_enabled),
        "webhook_url": _redact_url(config.webhook_url),
        "webhook_secret": _redact(config.webhook_secret),
    }


def _redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _redact_url(value: str) -> str:
    if not value:
        return ""
    return "***"
