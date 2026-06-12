import time
from collections.abc import Callable

from fastapi import HTTPException

from app.api.v1.health import dependency_health_check
from app.core.config import Settings, settings
from app.services.dependency_health_monitor import (
    DependencyHealthMonitorConfig,
    run_dependency_health_monitor_tick,
)
from app.services.external_alerts import ExternalAlertConfig


MonitorSleep = Callable[[int], None]


def dependency_monitor_config_from_settings(
    app_settings: Settings = settings,
) -> DependencyHealthMonitorConfig:
    return DependencyHealthMonitorConfig(
        enabled=app_settings.dependency_health_monitor_enabled,
        interval_seconds=app_settings.dependency_health_monitor_interval_seconds,
        throttle_seconds=app_settings.dependency_health_alert_throttle_seconds,
    )


def external_alert_config_from_settings(app_settings: Settings = settings) -> ExternalAlertConfig:
    return ExternalAlertConfig(
        telegram_enabled=app_settings.telegram_alerts_enabled,
        telegram_bot_token=app_settings.telegram_bot_token,
        telegram_chat_id=app_settings.telegram_chat_id,
        email_enabled=app_settings.email_alerts_enabled,
        smtp_host=app_settings.smtp_host,
        smtp_port=app_settings.smtp_port,
        smtp_username=app_settings.smtp_username,
        smtp_password=app_settings.smtp_password,
        alert_email_from=app_settings.alert_email_from,
        alert_email_to=app_settings.alert_email_to,
        webhook_enabled=app_settings.webhook_alerts_enabled,
        webhook_url=app_settings.alert_webhook_url,
        webhook_secret=app_settings.alert_webhook_secret,
        timeout_seconds=app_settings.alert_timeout_seconds,
    )


def collect_dependency_health() -> dict[str, str]:
    try:
        return dependency_health_check()
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            return {
                str(key): str(value)
                for key, value in detail.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return {"status": "degraded", "backend": "unavailable"}


def run_dependency_health_monitor_once(
    *,
    now_seconds: int | None = None,
    dispatch_state: dict[str, int] | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    resolved_now = int(time.time()) if now_seconds is None else now_seconds
    return run_dependency_health_monitor_tick(
        collect_dependency_health,
        external_alert_config_from_settings(),
        dependency_monitor_config_from_settings(),
        now_seconds=resolved_now,
        dispatch_state=dispatch_state,
        transports=transports,
    )


def run_dependency_health_monitor_forever(sleep: MonitorSleep = time.sleep) -> None:
    state: dict[str, int] = {}
    while True:
        monitor_config = dependency_monitor_config_from_settings()
        try:
            run_dependency_health_monitor_once(
                now_seconds=int(time.time()),
                dispatch_state=state,
            )
        except Exception:
            state["last_monitor_error_at"] = int(time.time())
        sleep(max(monitor_config.interval_seconds, 1))


if __name__ == "__main__":
    run_dependency_health_monitor_forever()
