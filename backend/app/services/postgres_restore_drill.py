from __future__ import annotations

import dataclasses
from pathlib import Path


class PostgresRestoreDrillError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class PostgresBackupVerificationResult:
    path: Path
    size_bytes: int
    has_postgres_dump_header: bool
    has_schema_statements: bool

    @property
    def valid(self) -> bool:
        return self.size_bytes > 0 and self.has_postgres_dump_header and self.has_schema_statements


def verify_plain_sql_backup(path: Path) -> PostgresBackupVerificationResult:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise PostgresRestoreDrillError(f"backup file does not exist: {resolved_path}")
    if not resolved_path.is_file():
        raise PostgresRestoreDrillError(f"backup path is not a file: {resolved_path}")

    size_bytes = resolved_path.stat().st_size
    if size_bytes <= 0:
        raise PostgresRestoreDrillError(f"backup file is empty: {resolved_path}")

    sample = _read_sample(resolved_path)
    result = PostgresBackupVerificationResult(
        path=resolved_path,
        size_bytes=size_bytes,
        has_postgres_dump_header="PostgreSQL database dump" in sample,
        has_schema_statements=_has_schema_statement(sample),
    )
    if not result.valid:
        raise PostgresRestoreDrillError("backup file failed plain SQL structure checks")
    return result


def _read_sample(path: Path, max_bytes: int = 1024 * 1024) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:max_bytes]


def _has_schema_statement(sample: str) -> bool:
    schema_markers = (
        "CREATE TABLE",
        "CREATE SCHEMA",
        "ALTER TABLE",
        "COPY ",
        "INSERT INTO",
    )
    return any(marker in sample for marker in schema_markers)
