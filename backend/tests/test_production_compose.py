with open("../docker-compose.prod.yml", encoding="utf-8") as compose_file:
    PRODUCTION_COMPOSE = compose_file.read()


def service_block(service_name: str) -> str:
    lines = PRODUCTION_COMPOSE.splitlines()
    marker = f"  {service_name}:"
    start = lines.index(marker)
    end = len(lines)

    for index, line in enumerate(lines[start + 1 :], start=start + 1):
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break

    return "\n".join(lines[start:end])


def test_dependency_health_monitor_service_is_guarded() -> None:
    block = service_block("dependency-health-monitor")

    assert "container_name: trading-prod-dependency-health-monitor" in block
    assert "restart: unless-stopped" in block
    assert "logging: *production-logging" in block
    assert "- monitoring" in block
    assert "- app.workers.dependency_health_monitor" in block
    assert "condition: service_healthy" in block


def test_dependency_health_monitor_service_keeps_safe_defaults() -> None:
    block = service_block("dependency-health-monitor")

    assert "TESTNET_ADAPTERS_ENABLED: ${TESTNET_ADAPTERS_ENABLED:-false}" in block
    expected_monitor_default = (
        "DEPENDENCY_HEALTH_MONITOR_ENABLED: "
        "${DEPENDENCY_HEALTH_MONITOR_ENABLED:-false}"
    )
    assert expected_monitor_default in block
    assert "TELEGRAM_ALERTS_ENABLED: ${TELEGRAM_ALERTS_ENABLED:-false}" in block
    assert "EMAIL_ALERTS_ENABLED: ${EMAIL_ALERTS_ENABLED:-false}" in block
    assert "WEBHOOK_ALERTS_ENABLED: ${WEBHOOK_ALERTS_ENABLED:-false}" in block
