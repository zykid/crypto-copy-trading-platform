"""add notification preferences

Revision ID: 202606120001
Revises: 202606090001
Create Date: 2026-06-12 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606120001"
down_revision: str | None = "202606090001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("internal_enabled", sa.Boolean(), nullable=False),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False),
        sa.Column("position_drift_enabled", sa.Boolean(), nullable=False),
        sa.Column("risk_rejection_enabled", sa.Boolean(), nullable=False),
        sa.Column("order_failure_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_preferences_user_id",
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
