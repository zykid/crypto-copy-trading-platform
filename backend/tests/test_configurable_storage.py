from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_STORAGE = (ROOT / "docker-compose.storage.yml").read_text(encoding="utf-8")
PROD_STORAGE = (ROOT / "docker-compose.prod.storage.yml").read_text(
    encoding="utf-8"
)
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
ENV_PROD_EXAMPLE = (ROOT / ".env.prod.example").read_text(encoding="utf-8")


def test_development_storage_override_is_explicit_and_scoped() -> None:
    assert "${TRADING_DATA_ROOT:?TRADING_DATA_ROOT must be an absolute host path}" in (
        DEV_STORAGE
    )
    assert "/postgres:/var/lib/postgresql/data" in DEV_STORAGE
    assert "/redis:/data" in DEV_STORAGE
    assert "docker compose down -v" not in DEV_STORAGE


def test_production_storage_override_covers_persistent_services() -> None:
    expected_targets = (
        "/postgres:/var/lib/postgresql/data",
        "/redis:/data",
        "/backups:/backups",
        "/caddy-data:/data",
        "/caddy-config:/config",
        "/prometheus:/prometheus",
        "/grafana:/var/lib/grafana",
    )

    for target in expected_targets:
        assert target in PROD_STORAGE

    assert "docker compose down -v" not in PROD_STORAGE


def test_storage_root_is_documented_in_environment_examples() -> None:
    assert "TRADING_DATA_ROOT=/mnt/trading-data" in ENV_EXAMPLE
    assert "TRADING_DATA_ROOT=/srv/trading/data" in ENV_PROD_EXAMPLE
