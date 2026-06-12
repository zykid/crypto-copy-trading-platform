from app.services.external_alerts import (
    ExternalAlertChannel,
    ExternalAlertConfig,
    build_external_alert_plan,
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
