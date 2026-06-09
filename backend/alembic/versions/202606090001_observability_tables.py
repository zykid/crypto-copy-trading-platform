"""add observability tables

Revision ID: 202606090001
Revises:
Create Date: 2026-06-09 12:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606090001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_exchange_account_id", "audit_logs", ["exchange_account_id"])
    op.create_index("ix_audit_logs_severity", "audit_logs", ["severity"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    op.create_table(
        "system_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])
    op.create_index(
        "ix_system_events_exchange_account_id", "system_events", ["exchange_account_id"]
    )
    op.create_index("ix_system_events_severity", "system_events", ["severity"])
    op.create_index("ix_system_events_user_id", "system_events", ["user_id"])

    op.create_table(
        "internal_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_internal_notifications_channel", "internal_notifications", ["channel"])
    op.create_index(
        "ix_internal_notifications_exchange_account_id",
        "internal_notifications",
        ["exchange_account_id"],
    )
    op.create_index("ix_internal_notifications_severity", "internal_notifications", ["severity"])
    op.create_index("ix_internal_notifications_user_id", "internal_notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_internal_notifications_user_id", table_name="internal_notifications")
    op.drop_index("ix_internal_notifications_severity", table_name="internal_notifications")
    op.drop_index("ix_internal_notifications_exchange_account_id", table_name="internal_notifications")
    op.drop_index("ix_internal_notifications_channel", table_name="internal_notifications")
    op.drop_table("internal_notifications")

    op.drop_index("ix_system_events_user_id", table_name="system_events")
    op.drop_index("ix_system_events_severity", table_name="system_events")
    op.drop_index("ix_system_events_exchange_account_id", table_name="system_events")
    op.drop_index("ix_system_events_event_type", table_name="system_events")
    op.drop_table("system_events")

    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_severity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_exchange_account_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
