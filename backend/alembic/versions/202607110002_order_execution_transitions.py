"""add append-only order execution transitions

Revision ID: 202607110002
Revises: 202607110001
Create Date: 2026-07-11 19:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607110002"
down_revision: str | None = "202607110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION_NAME = "prevent_order_execution_transitions_mutation"
TRIGGER_NAME = "trg_order_execution_transitions_append_only"


def upgrade() -> None:
    op.create_table(
        "order_execution_transitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("order_execution_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_execution_id"], ["order_executions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_execution_id", "sequence_number"),
    )
    op.create_index(
        "ix_order_execution_transitions_order_execution_id",
        "order_execution_transitions",
        ["order_execution_id"],
    )
    op.create_index(
        "ix_order_execution_transitions_user_id",
        "order_execution_transitions",
        ["user_id"],
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'order_execution_transitions is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE UPDATE OR DELETE ON order_execution_transitions
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}();
        """
    )


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON order_execution_transitions;"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}();")
    op.drop_index(
        "ix_order_execution_transitions_user_id",
        table_name="order_execution_transitions",
    )
    op.drop_index(
        "ix_order_execution_transitions_order_execution_id",
        table_name="order_execution_transitions",
    )
    op.drop_table("order_execution_transitions")
