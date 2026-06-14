import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.backup.retention_cleanup import (  # noqa: E402
    BackupRetentionCleanupError,
    cleanup_expired_backups,
    find_backup_candidates,
    parse_backup_date,
    select_expired_backups,
)


def test_parse_backup_date_accepts_expected_filename() -> None:
    assert parse_backup_date(Path("backup_20260614.sql")).isoformat() == "2026-06-14"


def test_parse_backup_date_rejects_unmanaged_names() -> None:
    assert parse_backup_date(Path("backup_latest.sql")) is None
    assert parse_backup_date(Path("notes.txt")) is None


def test_find_backup_candidates_only_returns_named_sql_files(tmp_path: Path) -> None:
    (tmp_path / "backup_20260610.sql").write_text("old", encoding="utf-8")
    (tmp_path / "backup_20260612.sql").write_text("new", encoding="utf-8")
    (tmp_path / "backup_latest.sql").write_text("ignored", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    candidates = find_backup_candidates(
        tmp_path,
        now=datetime(2026, 6, 14, tzinfo=UTC),
    )

    assert [candidate.path.name for candidate in candidates] == [
        "backup_20260610.sql",
        "backup_20260612.sql",
    ]


def test_select_expired_backups_uses_retention_cutoff(tmp_path: Path) -> None:
    (tmp_path / "backup_20260601.sql").write_text("expired", encoding="utf-8")
    (tmp_path / "backup_20260610.sql").write_text("kept", encoding="utf-8")

    expired = select_expired_backups(
        tmp_path,
        retention_days=7,
        now=datetime(2026, 6, 14, tzinfo=UTC),
    )

    assert [candidate.path.name for candidate in expired] == ["backup_20260601.sql"]


def test_cleanup_expired_backups_defaults_to_dry_run(tmp_path: Path) -> None:
    expired_file = tmp_path / "backup_20260601.sql"
    expired_file.write_text("expired", encoding="utf-8")

    result = cleanup_expired_backups(
        tmp_path,
        retention_days=7,
        now=datetime(2026, 6, 14, tzinfo=UTC),
    )

    assert result.dry_run is True
    assert [candidate.path.name for candidate in result.expired] == ["backup_20260601.sql"]
    assert result.deleted == ()
    assert expired_file.exists()


def test_cleanup_expired_backups_deletes_only_expired_named_files(tmp_path: Path) -> None:
    expired_file = tmp_path / "backup_20260601.sql"
    kept_file = tmp_path / "backup_20260613.sql"
    ignored_file = tmp_path / "backup_latest.sql"
    expired_file.write_text("expired", encoding="utf-8")
    kept_file.write_text("kept", encoding="utf-8")
    ignored_file.write_text("ignored", encoding="utf-8")

    result = cleanup_expired_backups(
        tmp_path,
        retention_days=7,
        dry_run=False,
        now=datetime(2026, 6, 14, tzinfo=UTC),
    )

    assert [path.name for path in result.deleted] == ["backup_20260601.sql"]
    assert not expired_file.exists()
    assert kept_file.exists()
    assert ignored_file.exists()


def test_cleanup_expired_backups_rejects_invalid_retention(tmp_path: Path) -> None:
    with pytest.raises(BackupRetentionCleanupError, match="at least 1"):
        select_expired_backups(tmp_path, retention_days=0)


def test_find_backup_candidates_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(BackupRetentionCleanupError, match="does not exist"):
        find_backup_candidates(tmp_path / "missing")
