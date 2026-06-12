from fastapi import HTTPException

from app.core.config import Settings
from app.services.dependency_health_monitor import DependencyHealthMonitorConfig
from app.services.external_alerts import ExternalAlertConfig, ExternalAlertTransports
from app.workers import dependency_health_monitor as worker


class CapturingHttpTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def post_json(
        self,
        url: str,
        payload: object,
        headers: object,
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


def test_dependency_monitor_config_from_settings() -> None:
    settings = Settings(
        dependency_health_monitor_enabled=True,
        dependency_health_monitor_interval_seconds=45,
        dependency_health_alert_throttle_seconds=600,
    )

    config = worker.dependency_monitor_config_from_settings(settings)

    assert config == DependencyHealthMonitorConfig(
        enabled=True,
        interval_seconds=45,
        throttle_seconds=600,
    )


def test_external_alert_config_from_settings_includes_timeout() -> None:
    settings = Settings(
        webhook_alerts_enabled=True,
        alert_webhook_url="https://alerts.example/hooks/token",
        alert_webhook_secret="webhook-secret",
        alert_timeout_seconds=2.5,
    )

    config = worker.external_alert_config_from_settings(settings)

    assert config.webhook_enabled is True
    assert config.webhook_url == "https://alerts.example/hooks/token"
    assert config.webhook_secret == "webhook-secret"
    assert config.timeout_seconds == 2.5


def test_collect_dependency_health_returns_sanitized_http_exception_detail(monkeypatch) -> None:
    def raise_health_error() -> dict[str, str]:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "database": "unavailable",
                "redis": "ok",
                "api_secret": {"nested": "secret"},
            },
        )

    monkeypatch.setattr(worker, "dependency_health_check", raise_health_error)

    assert worker.collect_dependency_health() == {
        "status": "degraded",
        "database": "unavailable",
        "redis": "ok",
    }


def test_run_dependency_health_monitor_once_dispatches_when_enabled(monkeypatch) -> None:
    http = CapturingHttpTransport()
    state: dict[str, int] = {}

    monkeypatch.setattr(
        worker,
        "dependency_monitor_config_from_settings",
        lambda: DependencyHealthMonitorConfig(enabled=True, interval_seconds=60, throttle_seconds=300),
    )
    monkeypatch.setattr(
        worker,
        "external_alert_config_from_settings",
        lambda: ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
            timeout_seconds=2,
        ),
    )
    monkeypatch.setattr(
        worker,
        "collect_dependency_health",
        lambda: {"status": "degraded", "database": "unavailable"},
    )

    results = worker.run_dependency_health_monitor_once(
        now_seconds=100,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert state == {"dependency_health": 100}
    assert http.requests[0]["timeout_seconds"] == 2
    assert http.requests[0]["payload"] == {
        "severity": "warning",
        "title": "Service dependency health degraded",
        "message": "One or more platform dependencies are not healthy.",
        "metadata": {
            "component": "health_check",
            "status": "degraded",
            "affected_dependencies": "database",
        },
    }
