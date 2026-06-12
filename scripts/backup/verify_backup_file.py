from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.postgres_restore_drill import (  # noqa: E402
    PostgresRestoreDrillError,
    verify_plain_sql_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a plain SQL PostgreSQL backup file.")
    parser.add_argument("backup_file", help="Path to backup_YYYYMMDD.sql")
    args = parser.parse_args()

    try:
        result = verify_plain_sql_backup(Path(args.backup_file))
    except PostgresRestoreDrillError as exc:
        print(f"Backup verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"Backup verification passed: {result.path}")
    print(f"Size bytes: {result.size_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
