import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.integration.ubuntu_preflight import (  # noqa: E402
    UbuntuIntegrationPreflightError,
    parse_env_text,
    run_preflight,
    validate_compose_safety,
    validate_env_values,
)


def test_parse_env_text_ignores_comments_and_blank_lines() -> None:
    values = parse_env_text(
        "# comment\n"
        "ENVIRONMENT=development\n"
        "\n"
        "TESTNET_ADAPTERS_ENABLED=false\n"
    )

    assert values == {
        "ENVIRONMENT": "development",
        "TESTNET_ADAPTERS_ENABLED": "false",
    }


def test_validate_env_values_rejects_testnet_enabled_for_mock_phase() -> None:
    with pytest.raises(UbuntuIntegrationPreflightError, match="must stay false"):
        validate_env_values({"TESTNET_ADAPTERS_ENABLED": "true"})


def test_validate_env_values_rejects_production_environment_for_mock_phase() -> None:
    with pytest.raises(UbuntuIntegrationPreflightError, match="development/mock"):
        validate_env_values({"ENVIRONMENT": "production"})


def test_validate_compose_safety_rejects_destructive_command() -> None:
    with pytest.raises(UbuntuIntegrationPreflightError, match="Forbidden"):
        validate_compose_safety("steps:\n  - docker compose down -v\n")


def test_run_preflight_accepts_safe_mock_repository(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "scripts" / "integration").mkdir(parents=True)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("ENVIRONMENT=development\n", encoding="utf-8")
    (tmp_path / "backend" / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (tmp_path / "frontend" / "Dockerfile").write_text("FROM node:22\n", encoding="utf-8")
    (tmp_path / "scripts" / "integration" / "mock_compose_check.py").write_text(
        "print('ok')\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ENVIRONMENT=development\nTESTNET_ADAPTERS_ENABLED=false\n",
        encoding="utf-8",
    )

    result = run_preflight(tmp_path, env_file)

    assert result.env_file == env_file.resolve()
    assert result.testnet_adapters_enabled is False
    assert "docker-compose.yml" in result.checked_files


def test_run_preflight_rejects_missing_env_file(tmp_path: Path) -> None:
    with pytest.raises(UbuntuIntegrationPreflightError, match="Environment file"):
        run_preflight(tmp_path, tmp_path / ".env")
