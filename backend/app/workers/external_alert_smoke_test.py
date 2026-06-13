from app.services.external_alerts import ExternalAlertEvent, send_external_alert
from app.workers.dependency_health_monitor import external_alert_config_from_settings


def build_external_alert_smoke_test_event() -> ExternalAlertEvent:
    return ExternalAlertEvent(
        severity="info",
        title="External alert smoke test",
        message="Synthetic operational alert delivery test.",
        metadata={
            "component": "external_alerts",
            "event_type": "smoke_test",
        },
    )


def run_external_alert_smoke_test(
    *,
    app_settings: object | None = None,
    transports: object | None = None,
) -> tuple[object, ...]:
    return send_external_alert(
        external_alert_config_from_settings(app_settings),
        build_external_alert_smoke_test_event(),
        transports,
    )


def main() -> int:
    results = run_external_alert_smoke_test()
    if not results:
        print("No external alert channels are enabled.")
        return 0

    failed = tuple(result for result in results if not result.delivered)
    for result in results:
        status = "delivered" if result.delivered else "failed"
        print(f"{result.channel.value}: {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
