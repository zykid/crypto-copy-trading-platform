"""add persistent global emergency stop

Revision ID: 202607110001
Revises: 202607010001
Create Date: 2026-07-11 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607110001"
down_revision: str | None = "202607010001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_controls",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column(
            "emergency_stop_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("changed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_controls_changed_by_user_id",
        "system_controls",
        ["changed_by_user_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO system_controls (id, emergency_stop_enabled, reason)
        VALUES ('global', false, 'Initial migration state')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_system_controls_changed_by_user_id", table_name="system_controls")
    op.drop_table("system_controls")
