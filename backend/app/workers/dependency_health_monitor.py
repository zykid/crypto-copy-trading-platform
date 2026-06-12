import time


def _resolved_settings(app_settings: object | None) -> object:
    if app_settings is not None:
        return app_settings

    from app.core.config import settings

    return settings


def dependency_monitor_config_from_settings(app_settings: object | None = None) -> object:
    from app.services.dependency_health_monitor import DependencyHealthMonitorConfig

    resolved_settings = _resolved_settings(app_settings)
    return DependencyHealthMonitorConfig(
        enabled=resolved_settings.dependency_health_monitor_enabled,
        interval_seconds=resolved_settings.dependency_health_monitor_interval_seconds,
        throttle_seconds=resolved_settings.dependency_health_alert_throttle_seconds,
    )


def external_alert_config_from_settings(app_settings: object | None = None) -> object:
    from app.services.external_alerts import ExternalAlertConfig

    resolved_settings = _resolved_settings(app_settings)
    return ExternalAlertConfig(
        telegram_enabled=resolved_settings.telegram_alerts_enabled,
        telegram_bot_token=resolved_settings.telegram_bot_token,
        telegram_chat_id=resolved_settings.telegram_chat_id,
        email_enabled=resolved_settings.email_alerts_enabled,
        smtp_host=resolved_settings.smtp_host,
        smtp_port=resolved_settings.smtp_port,
        smtp_username=resolved_settings.smtp_username,
        smtp_password=resolved_settings.smtp_password,
        alert_email_from=resolved_settings.alert_email_from,
        alert_email_to=resolved_settings.alert_email_to,
        webhook_enabled=resolved_settings.webhook_alerts_enabled,
        webhook_url=resolved_settings.alert_webhook_url,
        webhook_secret=resolved_settings.alert_webhook_secret,
        timeout_seconds=resolved_settings.alert_timeout_seconds,
    )


def collect_dependency_health() -> dict[str, str]:
    from fastapi import HTTPException

    from app.api.v1.health import dependency_health_check

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
    from app.services.dependency_health_monitor import run_dependency_health_monitor_tick

    resolved_now = int(time.time()) if now_seconds is None else now_seconds
    return run_dependency_health_monitor_tick(
        collect_dependency_health,
        external_alert_config_from_settings(),
        dependency_monitor_config_from_settings(),
        now_seconds=resolved_now,
        dispatch_state=dispatch_state,
        transports=transports,
    )


def run_dependency_health_monitor_forever(sleep=time.sleep) -> None:
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
