"""enforce audit log append-only writes

Revision ID: 202607010001
Revises: 202606200002
Create Date: 2026-07-01 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202607010001"
down_revision: str | None = "202606200002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION_NAME = "prevent_audit_logs_mutation"
TRIGGER_NAME = "trg_audit_logs_append_only"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON audit_logs;")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}();")
