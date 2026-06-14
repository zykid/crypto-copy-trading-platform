from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BACKUP_FILE_PATTERN = re.compile(r"^backup_(\d{8})\.sql$")
DEFAULT_RETENTION_DAYS = 30


class BackupRetentionCleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupCleanupCandidate:
    path: Path
    backup_date: date
    age_days: int


@dataclass(frozen=True)
class BackupCleanupResult:
    expired: tuple[BackupCleanupCandidate, ...]
    deleted: tuple[Path, ...]
    dry_run: bool


def parse_backup_date(path: Path) -> date | None:
    match = BACKUP_FILE_PATTERN.match(path.name)
    if match is None:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def find_backup_candidates(
    backup_dir: Path,
    *,
    now: datetime | None = None,
) -> tuple[BackupCleanupCandidate, ...]:
    if not backup_dir.exists():
        raise BackupRetentionCleanupError(f"Backup directory does not exist: {backup_dir}")
    if not backup_dir.is_dir():
        raise BackupRetentionCleanupError(f"Backup path is not a directory: {backup_dir}")

    reference_date = _reference_date(now)
    candidates: list[BackupCleanupCandidate] = []
    for path in backup_dir.iterdir():
        if not path.is_file():
            continue

        backup_date = parse_backup_date(path)
        if backup_date is None:
            continue

        candidates.append(
            BackupCleanupCandidate(
                path=path.resolve(),
                backup_date=backup_date,
                age_days=(reference_date - backup_date).days,
            )
        )

    return tuple(sorted(candidates, key=lambda candidate: candidate.backup_date))


def select_expired_backups(
    backup_dir: Path,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> tuple[BackupCleanupCandidate, ...]:
    if retention_days < 1:
        raise BackupRetentionCleanupError("Retention days must be at least 1")

    cutoff = _reference_date(now) - timedelta(days=retention_days)
    candidates = find_backup_candidates(backup_dir, now=now)
    return tuple(candidate for candidate in candidates if candidate.backup_date < cutoff)


def cleanup_expired_backups(
    backup_dir: Path,
    *,
    retention_days: int,
    dry_run: bool = True,
    now: datetime | None = None,
) -> BackupCleanupResult:
    expired = select_expired_backups(
        backup_dir,
        retention_days=retention_days,
        now=now,
    )
    deleted: list[Path] = []

    if not dry_run:
        for candidate in expired:
            if parse_backup_date(candidate.path) is None:
                raise BackupRetentionCleanupError(
                    f"Refusing to delete non-backup file: {candidate.path}"
                )
            candidate.path.unlink()
            deleted.append(candidate.path)

    return BackupCleanupResult(expired=expired, deleted=tuple(deleted), dry_run=dry_run)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Safely remove old backup_YYYYMMDD.sql files after review."
    )
    parser.add_argument(
        "--backup-dir",
        default=os.getenv("POSTGRES_BACKUP_DIR", "backups"),
        help="Directory containing backup_YYYYMMDD.sql files.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=_env_int("POSTGRES_BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS),
        help="Keep backups newer than this many days. Default: 30.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete expired backup files. Without this flag the command is a dry run.",
    )
    args = parser.parse_args(argv)

    try:
        result = cleanup_expired_backups(
            Path(args.backup_dir),
            retention_days=args.retention_days,
            dry_run=not args.apply,
        )
    except BackupRetentionCleanupError as exc:
        print(f"Backup retention cleanup failed: {exc}", file=sys.stderr)
        return 1

    mode = "apply" if args.apply else "dry-run"
    print(f"Backup retention cleanup mode: {mode}")
    print(f"Expired backup files: {len(result.expired)}")
    for candidate in result.expired:
        action = "deleted" if args.apply else "would delete"
        print(f"{action}: {candidate.path} age_days={candidate.age_days}")

    return 0


def _reference_date(now: datetime | None) -> date:
    if now is None:
        return datetime.now(UTC).date()
    return now.date()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
