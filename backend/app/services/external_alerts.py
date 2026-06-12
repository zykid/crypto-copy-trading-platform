import dataclasses
import hashlib
import hmac
import json
import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from enum import StrEnum
from urllib import parse, request


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
    timeout_seconds: float = 5.0


@dataclasses.dataclass(frozen=True)
class ExternalAlertEvent:
    severity: str
    title: str
    message: str
    metadata: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ExternalAlertDeliveryResult:
    channel: ExternalAlertChannel
    delivered: bool
    error_message: str = ""


@dataclasses.dataclass(frozen=True)
class ExternalAlertPlan:
    enabled_channels: tuple[ExternalAlertChannel, ...]
    validation_errors: tuple[str, ...]
    redacted_summary: dict[str, str]

    @property
    def ready(self) -> bool:
        return bool(self.enabled_channels) and not self.validation_errors


class ExternalAlertDeliveryError(RuntimeError):
    pass


class HttpAlertTransport:
    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            if status_code >= 400:
                raise ExternalAlertDeliveryError(f"HTTP alert returned status {status_code}")


class EmailAlertTransport:
    def send_email(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        email_message: EmailMessage,
        timeout_seconds: float,
    ) -> None:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=timeout_seconds) as smtp:
            smtp.starttls(context=context)
            smtp.login(username, password)
            smtp.send_message(email_message)


@dataclasses.dataclass(frozen=True)
class ExternalAlertTransports:
    http: HttpAlertTransport = dataclasses.field(default_factory=HttpAlertTransport)
    email: EmailAlertTransport = dataclasses.field(default_factory=EmailAlertTransport)


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


def send_external_alert(
    config: ExternalAlertConfig,
    event: ExternalAlertEvent,
    transports: ExternalAlertTransports | None = None,
) -> tuple[ExternalAlertDeliveryResult, ...]:
    plan = build_external_alert_plan(config)
    if not plan.enabled_channels:
        return ()
    if plan.validation_errors:
        joined_errors = ", ".join(plan.validation_errors)
        raise ExternalAlertDeliveryError(f"external alert config invalid: {joined_errors}")

    resolved_transports = transports or ExternalAlertTransports()
    safe_event = _sanitize_event(event)
    results: list[ExternalAlertDeliveryResult] = []

    for channel in plan.enabled_channels:
        try:
            if channel == ExternalAlertChannel.TELEGRAM:
                _send_telegram(config, safe_event, resolved_transports.http)
            elif channel == ExternalAlertChannel.EMAIL:
                _send_email(config, safe_event, resolved_transports.email)
            elif channel == ExternalAlertChannel.WEBHOOK:
                _send_webhook(config, safe_event, resolved_transports.http)
        except Exception as exc:
            results.append(
                ExternalAlertDeliveryResult(
                    channel=channel,
                    delivered=False,
                    error_message=_safe_error_message(exc),
                )
            )
        else:
            results.append(ExternalAlertDeliveryResult(channel=channel, delivered=True))

    return tuple(results)


def _send_telegram(
    config: ExternalAlertConfig,
    event: ExternalAlertEvent,
    transport: HttpAlertTransport,
) -> None:
    url = f"https://api.telegram.org/bot{parse.quote(config.telegram_bot_token)}/sendMessage"
    transport.post_json(
        url=url,
        payload={"chat_id": config.telegram_chat_id, "text": _format_plain_text(event)},
        headers={},
        timeout_seconds=config.timeout_seconds,
    )


def _send_email(
    config: ExternalAlertConfig,
    event: ExternalAlertEvent,
    transport: EmailAlertTransport,
) -> None:
    email_message = EmailMessage()
    email_message["From"] = config.alert_email_from
    email_message["To"] = config.alert_email_to
    email_message["Subject"] = f"[{event.severity.upper()}] {event.title}"
    email_message.set_content(_format_plain_text(event))
    transport.send_email(
        host=config.smtp_host,
        port=config.smtp_port,
        username=config.smtp_username,
        password=config.smtp_password,
        email_message=email_message,
        timeout_seconds=config.timeout_seconds,
    )


def _send_webhook(
    config: ExternalAlertConfig,
    event: ExternalAlertEvent,
    transport: HttpAlertTransport,
) -> None:
    payload = {
        "severity": event.severity,
        "title": event.title,
        "message": event.message,
        "metadata": dict(event.metadata),
    }
    headers = {}
    if config.webhook_secret:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(config.webhook_secret.encode("utf-8"), body, hashlib.sha256)
        headers["X-Alert-Signature"] = f"sha256={signature.hexdigest()}"
    transport.post_json(
        url=config.webhook_url,
        payload=payload,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
    )


def _sanitize_event(event: ExternalAlertEvent) -> ExternalAlertEvent:
    return ExternalAlertEvent(
        severity=_safe_text(event.severity),
        title=_safe_text(event.title),
        message=_safe_text(event.message),
        metadata={_safe_text(key): _safe_text(value) for key, value in event.metadata.items()},
    )


def _safe_text(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").strip()[:500]


def _format_plain_text(event: ExternalAlertEvent) -> str:
    lines = [f"severity: {event.severity}", f"title: {event.title}", f"message: {event.message}"]
    for key, value in sorted(event.metadata.items()):
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _safe_error_message(exc: Exception) -> str:
    return _redact_url(_safe_text(str(exc))) or exc.__class__.__name__


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
    if "://" in value:
        return "***"
    return value
