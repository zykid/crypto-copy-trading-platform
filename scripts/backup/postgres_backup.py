from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.external_alerts import (  # noqa: E402
    ExternalAlertConfig,
    ExternalAlertDeliveryError,
    ExternalAlertEvent,
    send_external_alert,
)
from app.services.postgres_backup import (  # noqa: E402
    PostgresBackupConfig,
    PostgresBackupError,
    run_pg_dump_backup,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL pg_dump backup.")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("POSTGRES_BACKUP_DIR", "backups"),
        help="Directory for backup_YYYYMMDD.sql output files.",
    )
    args = parser.parse_args(argv)

    config = PostgresBackupConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=_required_env("POSTGRES_DB"),
        username=_required_env("POSTGRES_USER"),
        password=_required_env("POSTGRES_PASSWORD"),
        output_dir=Path(args.output_dir),
    )

    try:
        output_path = run_pg_dump_backup(config)
    except (PostgresBackupError, ValueError) as exc:
        print(f"PostgreSQL backup failed: {exc.__class__.__name__}", file=sys.stderr)
        _send_backup_failure_alert(exc)
        return 1

    print(f"PostgreSQL backup created: {output_path}")
    return 0


def _send_backup_failure_alert(exc: Exception) -> None:
    config = _external_alert_config_from_env()
    if not _external_alerts_enabled(config):
        return

    event = ExternalAlertEvent(
        severity="critical",
        title="PostgreSQL backup failed",
        message="The scheduled PostgreSQL backup job failed.",
        metadata={
            "component": "postgres_backup",
            "error_type": exc.__class__.__name__,
        },
    )

    try:
        results = send_external_alert(config, event)
    except ExternalAlertDeliveryError as alert_exc:
        print(
            f"PostgreSQL backup alert failed: {alert_exc.__class__.__name__}",
            file=sys.stderr,
        )
        return

    for result in results:
        status = "delivered" if result.delivered else "failed"
        print(f"PostgreSQL backup alert {result.channel.value}: {status}", file=sys.stderr)


def _external_alert_config_from_env() -> ExternalAlertConfig:
    return ExternalAlertConfig(
        telegram_enabled=_env_bool("TELEGRAM_ALERTS_ENABLED"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        email_enabled=_env_bool("EMAIL_ALERTS_ENABLED"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        alert_email_from=os.getenv("ALERT_EMAIL_FROM", ""),
        alert_email_to=os.getenv("ALERT_EMAIL_TO", ""),
        webhook_enabled=_env_bool("WEBHOOK_ALERTS_ENABLED"),
        webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
        webhook_secret=os.getenv("ALERT_WEBHOOK_SECRET", ""),
        timeout_seconds=_env_float("ALERT_TIMEOUT_SECONDS", 5.0),
    )


def _external_alerts_enabled(config: ExternalAlertConfig) -> bool:
    return config.telegram_enabled or config.email_enabled or config.webhook_enabled


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
