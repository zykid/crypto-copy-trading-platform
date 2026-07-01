from pathlib import Path


def test_audit_log_append_only_migration_blocks_update_and_delete() -> None:
    migration = Path("alembic/versions/202607010001_audit_log_append_only.py")

    contents = migration.read_text(encoding="utf-8")

    assert 'FUNCTION_NAME = "prevent_audit_logs_mutation"' in contents
    assert 'TRIGGER_NAME = "trg_audit_logs_append_only"' in contents
    assert "CREATE OR REPLACE FUNCTION" in contents
    assert "CREATE TRIGGER" in contents
    assert "BEFORE UPDATE OR DELETE ON audit_logs" in contents
    assert "RAISE EXCEPTION 'audit_logs is append-only'" in contents
