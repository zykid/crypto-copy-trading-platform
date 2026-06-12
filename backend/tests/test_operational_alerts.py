from app.services.external_alerts import ExternalAlertConfig, ExternalAlertTransports
from app.services.operational_alerts import (
    build_dependency_health_alert,
    maybe_send_dependency_health_alert,
)


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


def test_dependency_health_alert_is_none_when_all_checks_ok() -> None:
    event = build_dependency_health_alert(
        {
            "status": "ok",
            "database": "ok",
            "redis": "ok",
        }
    )

    assert event is None


def test_dependency_health_alert_reports_safe_affected_dependencies() -> None:
    event = build_dependency_health_alert(
        {
            "status": "degraded",
            "database": "unavailable",
            "redis": "ok",
        }
    )

    assert event is not None
    assert event.severity == "warning"
    assert event.title == "Service dependency health degraded"
    assert event.message == "One or more platform dependencies are not healthy."
    assert event.metadata == {
        "component": "health_check",
        "status": "degraded",
        "affected_dependencies": "database",
    }


def test_dependency_health_alert_filters_unsafe_fields() -> None:
    event = build_dependency_health_alert(
        {
            "status": "down with secret-token",
            "database": "unavailable",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "api_secret": "super-secret",
            "redis": "leaked password",
        }
    )

    assert event is not None
    assert event.severity == "critical"
    assert event.metadata == {
        "component": "health_check",
        "status": "unknown",
        "affected_dependencies": "database,redis",
    }
    event_text = f"{event.title} {event.message} {event.metadata}"
    assert "super-secret" not in event_text
    assert "00000000-0000-0000-0000-000000000001" not in event_text
    assert "secret-token" not in event_text


def test_dependency_health_dispatch_does_not_send_when_checks_are_ok() -> None:
    http = CapturingHttpTransport()
    state: dict[str, int] = {}

    results = maybe_send_dependency_health_alert(
        {"status": "ok", "database": "ok", "redis": "ok"},
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        now_seconds=100,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert results == ()
    assert state == {}
    assert http.requests == []


def test_dependency_health_dispatch_sends_safe_event_when_unhealthy() -> None:
    http = CapturingHttpTransport()
    state: dict[str, int] = {}

    results = maybe_send_dependency_health_alert(
        {"status": "degraded", "database": "unavailable", "redis": "ok"},
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        now_seconds=100,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert state == {"dependency_health": 100}
    assert len(http.requests) == 1
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


def test_dependency_health_dispatch_is_throttled_within_window() -> None:
    http = CapturingHttpTransport()
    state = {"dependency_health": 100}

    results = maybe_send_dependency_health_alert(
        {"status": "degraded", "database": "unavailable"},
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        now_seconds=200,
        throttle_seconds=300,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert results == ()
    assert state == {"dependency_health": 100}
    assert http.requests == []


def test_dependency_health_dispatch_sends_again_after_throttle_window() -> None:
    http = CapturingHttpTransport()
    state = {"dependency_health": 100}

    results = maybe_send_dependency_health_alert(
        {"status": "unavailable", "database": "unavailable"},
        ExternalAlertConfig(webhook_enabled=True, webhook_url="https://alerts.example/hooks/token"),
        now_seconds=401,
        throttle_seconds=300,
        dispatch_state=state,
        transports=ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert state == {"dependency_health": 401}
    assert len(http.requests) == 1
