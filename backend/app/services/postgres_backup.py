from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from os import environ
from pathlib import Path
from subprocess import CompletedProcess, run


DEFAULT_BACKUP_PREFIX = "backup"


class PostgresBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class PostgresBackupConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    output_dir: Path
    filename_prefix: str = DEFAULT_BACKUP_PREFIX


@dataclass(frozen=True)
class PostgresBackupPlan:
    command: tuple[str, ...]
    env: Mapping[str, str]
    output_path: Path


Runner = Callable[..., CompletedProcess[str]]


def plan_pg_dump_backup(
    config: PostgresBackupConfig,
    *,
    backup_date: date | None = None,
) -> PostgresBackupPlan:
    _validate_config(config)
    selected_date = backup_date or datetime.now(UTC).date()
    output_path = config.output_dir / f"{config.filename_prefix}_{selected_date:%Y%m%d}.sql"
    command = (
        "pg_dump",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--username",
        config.username,
        "--dbname",
        config.database,
        "--file",
        str(output_path),
        "--format",
        "plain",
        "--no-owner",
        "--no-privileges",
    )
    return PostgresBackupPlan(
        command=command,
        env={"PGPASSWORD": config.password},
        output_path=output_path,
    )


def run_pg_dump_backup(
    config: PostgresBackupConfig,
    *,
    backup_date: date | None = None,
    runner: Runner = run,
) -> Path:
    plan = plan_pg_dump_backup(config, backup_date=backup_date)
    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    env = environ.copy()
    env.update(plan.env)
    result = runner(
        plan.command,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = _redact_secret(result.stderr or "pg_dump failed", config.password)
        raise PostgresBackupError(stderr)
    return plan.output_path


def _validate_config(config: PostgresBackupConfig) -> None:
    required_values = {
        "host": config.host,
        "database": config.database,
        "username": config.username,
        "password": config.password,
        "filename_prefix": config.filename_prefix,
    }
    missing = tuple(name for name, value in required_values.items() if not value)
    if missing:
        raise ValueError(f"missing PostgreSQL backup config: {', '.join(missing)}")
    if config.port <= 0:
        raise ValueError("PostgreSQL backup port must be positive")


def _redact_secret(value: str, secret: str) -> str:
    if not secret:
        return value
    return value.replace(secret, "***")
