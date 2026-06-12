from app.services.operational_alerts import build_dependency_health_alert


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
