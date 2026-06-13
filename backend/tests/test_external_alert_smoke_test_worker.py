from app.core.config import Settings
from app.services.external_alerts import ExternalAlertTransports
from app.workers import external_alert_smoke_test as worker


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


class FailingHttpTransport:
    def post_json(
        self,
        url: str,
        payload: object,
        headers: object,
        timeout_seconds: float,
    ) -> None:
        raise RuntimeError("network down https://alerts.example/hooks/secret-token")


def test_smoke_test_event_contains_only_safe_operational_fields() -> None:
    event = worker.build_external_alert_smoke_test_event()

    assert event.severity == "info"
    assert event.title == "External alert smoke test"
    assert event.message == "Synthetic operational alert delivery test."
    assert event.metadata == {
        "component": "external_alerts",
        "event_type": "smoke_test",
    }


def test_smoke_test_does_not_send_when_all_channels_are_disabled() -> None:
    http = CapturingHttpTransport()

    results = worker.run_external_alert_smoke_test(
        app_settings=Settings(),
        transports=ExternalAlertTransports(http=http),
    )

    assert results == ()
    assert http.requests == []


def test_smoke_test_sends_safe_webhook_payload_when_enabled() -> None:
    http = CapturingHttpTransport()

    results = worker.run_external_alert_smoke_test(
        app_settings=Settings(
            webhook_alerts_enabled=True,
            alert_webhook_url="https://alerts.example/hooks/token",
            alert_timeout_seconds=2,
        ),
        transports=ExternalAlertTransports(http=http),
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert len(http.requests) == 1
    assert http.requests[0]["timeout_seconds"] == 2
    assert http.requests[0]["payload"] == {
        "severity": "info",
        "title": "External alert smoke test",
        "message": "Synthetic operational alert delivery test.",
        "metadata": {
            "component": "external_alerts",
            "event_type": "smoke_test",
        },
    }


def test_smoke_test_redacts_delivery_errors() -> None:
    results = worker.run_external_alert_smoke_test(
        app_settings=Settings(
            webhook_alerts_enabled=True,
            alert_webhook_url="https://alerts.example/hooks/token",
        ),
        transports=ExternalAlertTransports(http=FailingHttpTransport()),
    )

    assert len(results) == 1
    assert results[0].delivered is False
    assert results[0].error_message == "network down ***"


def test_smoke_test_main_returns_failure_when_delivery_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        worker,
        "run_external_alert_smoke_test",
        lambda: (type("Result", (), {"delivered": False, "channel": "webhook"})(),),
    )

    assert worker.main() == 1
