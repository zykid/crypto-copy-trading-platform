from app.services.dependency_health_monitor import (
    DependencyHealthMonitorConfig,
    build_dependency_health_monitor_plan,
    run_dependency_health_monitor_tick,
)
from app.services.external_alerts import ExternalAlertConfig, ExternalAlertTransports


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


def test_dependency_health_monitor_is_disabled_by_default() -> None:
    plan = build_dependency_health_monitor_plan(DependencyHealthMonitorConfig())

    assert plan.enabled is False
    assert plan.ready is False
    assert plan.interval_seconds == 60
    assert plan.throttle_seconds == 300
    assert plan.validation_errors == ()


def test_dependency_health_monitor_validates_interval_and_throttle() -> None:
    plan = build_dependency_health_monitor_plan(
        DependencyHealthMonitorConfig(
            enabled=True,
            interval_seconds=0,
            throttle_seconds=-1,
        )
    )

    assert plan.ready is False
    assert "dependency health monitor interval must be positive" in plan.validation_errors
    assert "dependency health alert throttle must not be negative" in plan.validation_errors


def test_dependency_health_monitor_does_not_call_provider_when_disabled() -> None:
    provider_called = False

    def checks_provider() -> dict[str, str]:
        nonlocal provider_called
        provider_called = True
        return {"status": "degraded", "database": "unavailable"}

    results = run_dependency_health_monitor_tick(
        checks_provider,
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        DependencyHealthMonitorConfig(enabled=False),
        now_seconds=100,
    )

    assert results == ()
    assert provider_called is False


def test_dependency_health_monitor_dispatches_when_enabled() -> None:
    http = CapturingHttpTransport()
    state: dict[str, int] = {}

    def checks_provider() -> dict[str, str]:
        return {"status": "degraded", "database": "unavailable", "redis": "ok"}

    results = run_dependency_health_monitor_tick(
        checks_provider,
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        DependencyHealthMonitorConfig(enabled=True, interval_seconds=60, throttle_seconds=300),
        now_seconds=100,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert state == {"dependency_health": 100}
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
