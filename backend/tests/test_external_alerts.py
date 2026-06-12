from email.message import EmailMessage
from typing import Any

import pytest

from app.services.external_alerts import (
    ExternalAlertChannel,
    ExternalAlertConfig,
    ExternalAlertDeliveryError,
    ExternalAlertEvent,
    ExternalAlertTransports,
    build_external_alert_plan,
    send_external_alert,
)


class FakeHttpTransport:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.requests: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> None:
        self.requests.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.should_fail:
            raise RuntimeError("https://alerts.example.com/private-token failed")


class FakeEmailTransport:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_email(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        email_message: EmailMessage,
        timeout_seconds: float,
    ) -> None:
        self.messages.append(
            {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "email_message": email_message,
                "timeout_seconds": timeout_seconds,
            }
        )


def test_external_alert_plan_is_disabled_by_default() -> None:
    plan = build_external_alert_plan(ExternalAlertConfig())

    assert plan.enabled_channels == ()
    assert plan.validation_errors == ()
    assert plan.ready is False


def test_external_alert_plan_validates_enabled_telegram_channel() -> None:
    plan = build_external_alert_plan(ExternalAlertConfig(telegram_enabled=True))

    assert plan.enabled_channels == (ExternalAlertChannel.TELEGRAM,)
    assert "telegram_bot_token is required" in plan.validation_errors
    assert "telegram_chat_id is required" in plan.validation_errors
    assert plan.ready is False


def test_external_alert_plan_marks_complete_channels_ready() -> None:
    plan = build_external_alert_plan(
        ExternalAlertConfig(
            telegram_enabled=True,
            telegram_bot_token="1234567890:secret-token",
            telegram_chat_id="123456789",
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        )
    )

    assert plan.enabled_channels == (
        ExternalAlertChannel.TELEGRAM,
        ExternalAlertChannel.WEBHOOK,
    )
    assert plan.validation_errors == ()
    assert plan.ready is True


def test_external_alert_plan_redacts_secrets_from_summary() -> None:
    config = ExternalAlertConfig(
        telegram_enabled=True,
        telegram_bot_token="1234567890:secret-token",
        telegram_chat_id="123456789",
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_username="alerts@example.com",
        smtp_password="mail-secret",
        alert_email_from="alerts@example.com",
        alert_email_to="ops@example.com",
        webhook_enabled=True,
        webhook_url="https://alerts.example/hooks/token",
        webhook_secret="webhook-secret",
    )

    plan = build_external_alert_plan(config)

    summary_text = " ".join(plan.redacted_summary.values())
    assert "1234567890:secret-token" not in summary_text
    assert "mail-secret" not in summary_text
    assert "https://alerts.example/hooks/token" not in summary_text
    assert "webhook-secret" not in summary_text
    assert "smtp.example.com" in summary_text


def test_external_alert_plan_rejects_invalid_email_port() -> None:
    plan = build_external_alert_plan(
        ExternalAlertConfig(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=0,
            smtp_username="alerts@example.com",
            smtp_password="mail-secret",
            alert_email_from="alerts@example.com",
            alert_email_to="ops@example.com",
        )
    )

    assert plan.enabled_channels == (ExternalAlertChannel.EMAIL,)
    assert "smtp_port must be positive" in plan.validation_errors
    assert plan.ready is False


def test_send_external_alert_does_nothing_when_all_channels_disabled() -> None:
    http = FakeHttpTransport()
    email = FakeEmailTransport()

    results = send_external_alert(
        ExternalAlertConfig(),
        ExternalAlertEvent(severity="warning", title="Backup failed", message="backup job failed"),
        ExternalAlertTransports(http=http, email=email),
    )

    assert results == ()
    assert http.requests == []
    assert email.messages == []


def test_send_external_alert_rejects_invalid_enabled_config_before_delivery() -> None:
    http = FakeHttpTransport()

    with pytest.raises(ExternalAlertDeliveryError):
        send_external_alert(
            ExternalAlertConfig(webhook_enabled=True),
            ExternalAlertEvent(severity="critical", title="Service unhealthy", message="backend down"),
            ExternalAlertTransports(http=http),
        )

    assert http.requests == []


def test_send_external_alert_delivers_to_all_enabled_channels() -> None:
    http = FakeHttpTransport()
    email = FakeEmailTransport()
    config = ExternalAlertConfig(
        telegram_enabled=True,
        telegram_bot_token="1234567890:secret-token",
        telegram_chat_id="123456789",
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_username="alerts@example.com",
        smtp_password="mail-secret",
        alert_email_from="alerts@example.com",
        alert_email_to="ops@example.com",
        webhook_enabled=True,
        webhook_url="https://alerts.example/hooks/token",
        webhook_secret="webhook-secret",
        timeout_seconds=3,
    )

    results = send_external_alert(
        config,
        ExternalAlertEvent(
            severity="critical",
            title="Emergency stop enabled",
            message="new orders are blocked",
            metadata={"scope": "global"},
        ),
        ExternalAlertTransports(http=http, email=email),
    )

    assert tuple(result.channel for result in results) == (
        ExternalAlertChannel.TELEGRAM,
        ExternalAlertChannel.EMAIL,
        ExternalAlertChannel.WEBHOOK,
    )
    assert all(result.delivered for result in results)
    assert len(http.requests) == 2
    assert len(email.messages) == 1
    assert http.requests[0]["payload"]["chat_id"] == "123456789"
    assert "X-Alert-Signature" in http.requests[1]["headers"]
    assert email.messages[0]["email_message"]["Subject"] == "[CRITICAL] Emergency stop enabled"


def test_send_external_alert_sanitizes_newlines_in_event_content() -> None:
    http = FakeHttpTransport()

    send_external_alert(
        ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        ),
        ExternalAlertEvent(
            severity="critical\nextra",
            title="Backup\nfailed",
            message="line one\nline two",
            metadata={"job\nname": "backup\njob"},
        ),
        ExternalAlertTransports(http=http),
    )

    payload = http.requests[0]["payload"]
    assert payload["severity"] == "critical extra"
    assert payload["title"] == "Backup failed"
    assert payload["message"] == "line one line two"
    assert payload["metadata"] == {"job name": "backup job"}


def test_send_external_alert_returns_redacted_failure_without_raising() -> None:
    http = FakeHttpTransport(should_fail=True)

    results = send_external_alert(
        ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        ),
        ExternalAlertEvent(severity="warning", title="Webhook failed", message="send failed"),
        ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].channel == ExternalAlertChannel.WEBHOOK
    assert results[0].delivered is False
    assert "https://alerts.example.com/private-token" not in results[0].error_message
