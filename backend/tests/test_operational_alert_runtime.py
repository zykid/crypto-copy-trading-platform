from app.services.external_alerts import ExternalAlertConfig, ExternalAlertTransports
from app.services.operational_alert_runtime import OperationalAlertRuntime


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


def test_runtime_sends_emergency_stop_alert_and_shares_throttle_state() -> None:
    http = CapturingHttpTransport()
    now = {"value": 100}
    runtime = OperationalAlertRuntime(
        ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        ),
        dispatch_state={},
        now_seconds_factory=lambda: now["value"],
        transports=ExternalAlertTransports(http=http),
    )

    first_results = runtime.notify_emergency_stop_enabled(scope="global")
    now["value"] = 200
    second_results = runtime.notify_emergency_stop_enabled(scope="global")

    assert len(first_results) == 1
    assert first_results[0].delivered is True
    assert second_results == ()
    assert runtime.dispatch_state == {"emergency_stop:global": 100}
    assert len(http.requests) == 1
    assert http.requests[0]["payload"] == {
        "severity": "critical",
        "title": "Emergency stop enabled",
        "message": "New trading, copy trading, and strategy execution are blocked.",
        "metadata": {
            "component": "kill_switch",
            "scope": "global",
            "new_orders_blocked": "true",
        },
    }


def test_runtime_keeps_alert_delivery_non_blocking_when_config_is_invalid() -> None:
    runtime = OperationalAlertRuntime(
        ExternalAlertConfig(webhook_enabled=True),
        now_seconds_factory=lambda: 100,
    )

    results = runtime.notify_order_failure(
        status="FAILED",
        failure_type="exchange_failed",
    )

    assert results == ()
    assert runtime.dispatch_state == {}


def test_runtime_sends_rate_limit_alert_with_safe_payload() -> None:
    http = CapturingHttpTransport()
    runtime = OperationalAlertRuntime(
        ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        ),
        now_seconds_factory=lambda: 100,
        transports=ExternalAlertTransports(http=http),
    )

    results = runtime.notify_rate_limit(
        exchange_name="binance",
        scope="account",
        request_category="order",
        retry_after_seconds=5,
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert runtime.dispatch_state == {"rate_limit:binance:account:order": 100}
    assert http.requests[0]["payload"] == {
        "severity": "warning",
        "title": "Rate limit protection triggered",
        "message": "Runtime rate-limit protection blocked an outbound exchange request.",
        "metadata": {
            "component": "rate_limit",
            "exchange": "binance",
            "scope": "account",
            "request_category": "order",
            "retry_after_seconds": "5",
        },
    }


def test_runtime_sends_reconciliation_drift_alert_with_safe_payload() -> None:
    http = CapturingHttpTransport()
    runtime = OperationalAlertRuntime(
        ExternalAlertConfig(
            webhook_enabled=True,
            webhook_url="https://alerts.example/hooks/token",
        ),
        now_seconds_factory=lambda: 100,
        transports=ExternalAlertTransports(http=http),
    )

    results = runtime.notify_reconciliation_drift(
        status="DRIFT_DETECTED",
        severity="CRITICAL",
        difference_count=2,
    )

    assert len(results) == 1
    assert results[0].delivered is True
    assert runtime.dispatch_state == {"reconciliation_drift:CRITICAL": 100}
    assert http.requests[0]["payload"] == {
        "severity": "critical",
        "title": "Position reconciliation drift detected",
        "message": "Position reconciliation detected drift that requires operator review.",
        "metadata": {
            "component": "position_reconciliation",
            "status": "DRIFT_DETECTED",
            "severity": "CRITICAL",
            "difference_count": "2",
            "auto_fix_allowed": "false",
        },
    }
