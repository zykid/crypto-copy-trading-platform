import pathlib
import re


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]
PRODUCTION_COMPOSE = (REPOSITORY_ROOT / "docker-compose.prod.yml").read_text()


def service_block(service_name: str) -> str:
    pattern = re.compile(rf"^  {re.escape(service_name)}:\n", re.MULTILINE)
    match = pattern.search(PRODUCTION_COMPOSE)
    assert match is not None

    next_match = re.search(
        r"^  [A-Za-z0-9_-]+:\n",
        PRODUCTION_COMPOSE[match.end() :],
        re.MULTILINE,
    )
    if next_match is None:
        return PRODUCTION_COMPOSE[match.start() :]
    return PRODUCTION_COMPOSE[match.start() : match.end() + next_match.start()]


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
