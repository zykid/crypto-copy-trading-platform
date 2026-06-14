from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REQUIRED_REPO_FILES = (
    "docker-compose.yml",
    ".env.example",
    "backend/Dockerfile",
    "frontend/Dockerfile",
    "scripts/integration/mock_compose_check.py",
)

FORBIDDEN_COMMANDS = (
    "docker system prune",
    "docker volume prune",
    "docker network prune",
    "docker compose down -v",
)

SAFE_TESTNET_VALUES = {"", "0", "false", "no", "off"}


class UbuntuIntegrationPreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class UbuntuIntegrationPreflightResult:
    checked_files: tuple[str, ...]
    env_file: Path
    testnet_adapters_enabled: bool


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_env_values(values: Mapping[str, str]) -> bool:
    testnet_value = values.get("TESTNET_ADAPTERS_ENABLED", "false").strip().lower()
    if testnet_value not in SAFE_TESTNET_VALUES:
        raise UbuntuIntegrationPreflightError(
            "TESTNET_ADAPTERS_ENABLED must stay false during Ubuntu mock integration"
        )

    if values.get("ENVIRONMENT", "development").strip().lower() == "production":
        raise UbuntuIntegrationPreflightError(
            "Use the development/mock compose environment for phase 2 integration"
        )

    return testnet_value not in SAFE_TESTNET_VALUES


def validate_required_files(repo_root: Path) -> tuple[str, ...]:
    missing = [path for path in REQUIRED_REPO_FILES if not (repo_root / path).exists()]
    if missing:
        raise UbuntuIntegrationPreflightError(
            "Missing required repository files: " + ", ".join(missing)
        )
    return REQUIRED_REPO_FILES


def validate_compose_safety(compose_text: str) -> None:
    lowered = compose_text.lower()
    for command in FORBIDDEN_COMMANDS:
        if command in lowered:
            raise UbuntuIntegrationPreflightError(
                f"Forbidden destructive Docker command found: {command}"
            )


def run_preflight(repo_root: Path, env_file: Path) -> UbuntuIntegrationPreflightResult:
    repo_root = repo_root.resolve()
    env_file = env_file.resolve()

    checked_files = validate_required_files(repo_root)
    if not env_file.exists():
        raise UbuntuIntegrationPreflightError(
            f"Environment file does not exist: {env_file}. Copy .env.example to .env first."
        )

    values = parse_env_text(env_file.read_text(encoding="utf-8"))
    testnet_enabled = validate_env_values(values)
    validate_compose_safety((repo_root / "docker-compose.yml").read_text(encoding="utf-8"))

    return UbuntuIntegrationPreflightResult(
        checked_files=tuple(checked_files),
        env_file=env_file,
        testnet_adapters_enabled=testnet_enabled,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Ubuntu mock integration prerequisites before starting containers."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root on the Ubuntu server.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Local environment file copied from .env.example.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = repo_root / env_file

    try:
        result = run_preflight(repo_root, env_file)
    except UbuntuIntegrationPreflightError as exc:
        print(f"Ubuntu integration preflight failed: {exc}", file=sys.stderr)
        return 1

    print("Ubuntu integration preflight passed")
    print(f"Environment file: {result.env_file}")
    print(f"Checked files: {len(result.checked_files)}")
    print("TESTNET adapters enabled: false")
    print("Next: docker compose up --build -d postgres redis backend frontend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
