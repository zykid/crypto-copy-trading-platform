from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.postgres_backup import (  # noqa: E402
    PostgresBackupConfig,
    PostgresBackupError,
    run_pg_dump_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL pg_dump backup.")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("POSTGRES_BACKUP_DIR", "backups"),
        help="Directory for backup_YYYYMMDD.sql output files.",
    )
    args = parser.parse_args()

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
        print(f"PostgreSQL backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"PostgreSQL backup created: {output_path}")
    return 0


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
