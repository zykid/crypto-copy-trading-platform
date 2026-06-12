from pathlib import Path

import pytest

from app.services.postgres_restore_drill import (
    PostgresRestoreDrillError,
    verify_plain_sql_backup,
)


def test_verify_plain_sql_backup_accepts_pg_dump_like_file(tmp_path: Path) -> None:
    backup_file = tmp_path / "backup_20260612.sql"
    backup_file.write_text(
        "--\n"
        "-- PostgreSQL database dump\n"
        "--\n"
        "CREATE TABLE public.users (id uuid NOT NULL);\n",
        encoding="utf-8",
    )

    result = verify_plain_sql_backup(backup_file)

    assert result.valid is True
    assert result.size_bytes > 0
    assert result.has_postgres_dump_header is True
    assert result.has_schema_statements is True


def test_verify_plain_sql_backup_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PostgresRestoreDrillError, match="does not exist"):
        verify_plain_sql_backup(tmp_path / "missing.sql")


def test_verify_plain_sql_backup_rejects_empty_file(tmp_path: Path) -> None:
    backup_file = tmp_path / "backup_20260612.sql"
    backup_file.write_text("", encoding="utf-8")

    with pytest.raises(PostgresRestoreDrillError, match="empty"):
        verify_plain_sql_backup(backup_file)


def test_verify_plain_sql_backup_rejects_non_dump_content(tmp_path: Path) -> None:
    backup_file = tmp_path / "backup_20260612.sql"
    backup_file.write_text("not a database dump", encoding="utf-8")

    with pytest.raises(PostgresRestoreDrillError, match="structure checks"):
        verify_plain_sql_backup(backup_file)
