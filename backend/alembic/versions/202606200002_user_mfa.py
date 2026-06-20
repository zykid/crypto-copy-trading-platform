"""add user mfa fields

Revision ID: 202606200002
Revises: 202606200001
Create Date: 2026-06-20 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606200002"
down_revision: str | None = "202606200001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("mfa_secret_encrypted", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_pending_secret_encrypted",
            sa.String(length=512),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("mfa_last_used_step", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_recovery_code_hashes",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_recovery_code_hashes")
    op.drop_column("users", "mfa_last_used_step")
    op.drop_column("users", "mfa_pending_secret_encrypted")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
