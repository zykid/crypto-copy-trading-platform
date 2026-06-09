"""add initial schema with observability tables

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
    _create_users()
    _create_exchange_accounts()
    _create_trading_tables()
    _create_observability_tables()


def downgrade() -> None:
    _drop_observability_tables()
    _drop_trading_tables()
    _drop_exchange_accounts()
    _drop_users()


def _create_index(
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    op.create_index(name, table_name, columns, unique=unique)


def _drop_index(name: str, table_name: str) -> None:
    op.drop_index(name, table_name=table_name)


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index("ix_users_email", "users", ["email"], unique=True)
    _create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("grantee_user_id", sa.String(length=36), nullable=False),
        sa.Column("view_only", sa.Boolean(), nullable=False),
        sa.Column("copy_follow", sa.Boolean(), nullable=False),
        sa.Column("pause_follow", sa.Boolean(), nullable=False),
        sa.Column("edit_copy_rule", sa.Boolean(), nullable=False),
        sa.Column("trade_manual", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["grantee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "grantee_user_id"),
    )
    _create_index(
        "ix_user_permissions_grantee_user_id",
        "user_permissions",
        ["grantee_user_id"],
    )
    _create_index(
        "ix_user_permissions_owner_user_id",
        "user_permissions",
        ["owner_user_id"],
    )


def _drop_users() -> None:
    _drop_index("ix_user_permissions_owner_user_id", "user_permissions")
    _drop_index("ix_user_permissions_grantee_user_id", "user_permissions")
    op.drop_table("user_permissions")
    _drop_index("ix_users_username", "users")
    _drop_index("ix_users_email", "users")
    op.drop_table("users")


def _create_exchange_accounts() -> None:
    op.create_table(
        "exchange_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_name", sa.String(length=40), nullable=False),
        sa.Column("account_mode", sa.String(length=40), nullable=False),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index("ix_exchange_accounts_user_id", "exchange_accounts", ["user_id"])

    op.create_table(
        "api_key_secrets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=False),
        sa.Column("encrypted_api_key", sa.String(length=512), nullable=False),
        sa.Column("encrypted_api_secret", sa.String(length=512), nullable=False),
        sa.Column("encrypted_passphrase", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_account_id"),
    )
    _create_index(
        "ix_api_key_secrets_exchange_account_id",
        "api_key_secrets",
        ["exchange_account_id"],
    )
    _create_index("ix_api_key_secrets_user_id", "api_key_secrets", ["user_id"])


def _drop_exchange_accounts() -> None:
    _drop_index("ix_api_key_secrets_user_id", "api_key_secrets")
    _drop_index("ix_api_key_secrets_exchange_account_id", "api_key_secrets")
    op.drop_table("api_key_secrets")
    _drop_index("ix_exchange_accounts_user_id", "exchange_accounts")
    op.drop_table("exchange_accounts")


def _create_trading_tables() -> None:
    op.create_table(
        "trading_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=40), nullable=False),
        sa.Column("order_type", sa.String(length=40), nullable=False),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("target_position_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index("ix_trading_signals_user_id", "trading_signals", ["user_id"])

    op.create_table(
        "risk_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=False),
        sa.Column("trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("max_single_order_notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_position_notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_leverage", sa.Numeric(12, 4), nullable=True),
        sa.Column("min_order_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_order_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("blocked_symbols", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_account_id"),
    )
    _create_index(
        "ix_risk_settings_exchange_account_id",
        "risk_settings",
        ["exchange_account_id"],
    )
    _create_index("ix_risk_settings_user_id", "risk_settings", ["user_id"])

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_account_id", "symbol"),
    )
    _create_index("ix_positions_exchange_account_id", "positions", ["exchange_account_id"])
    _create_index("ix_positions_user_id", "positions", ["user_id"])

    op.create_table(
        "order_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("signal_id", sa.String(length=36), nullable=True),
        sa.Column("execution_id", sa.String(length=36), nullable=True),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=True),
        sa.Column("exchange_name", sa.String(length=40), nullable=False),
        sa.Column("client_order_id", sa.String(length=80), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=120), nullable=True),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=40), nullable=False),
        sa.Column("order_type", sa.String(length=40), nullable=False),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_result", sa.JSON(), nullable=True),
        sa.Column("exchange_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["trading_signals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
        sa.UniqueConstraint("execution_id"),
        sa.UniqueConstraint("signal_id", "exchange_account_id"),
    )
    _create_index(
        "ix_order_executions_exchange_account_id",
        "order_executions",
        ["exchange_account_id"],
    )
    _create_index("ix_order_executions_signal_id", "order_executions", ["signal_id"])
    _create_index("ix_order_executions_user_id", "order_executions", ["user_id"])


def _drop_trading_tables() -> None:
    _drop_index("ix_order_executions_user_id", "order_executions")
    _drop_index("ix_order_executions_signal_id", "order_executions")
    _drop_index("ix_order_executions_exchange_account_id", "order_executions")
    op.drop_table("order_executions")
    _drop_index("ix_positions_user_id", "positions")
    _drop_index("ix_positions_exchange_account_id", "positions")
    op.drop_table("positions")
    _drop_index("ix_risk_settings_user_id", "risk_settings")
    _drop_index("ix_risk_settings_exchange_account_id", "risk_settings")
    op.drop_table("risk_settings")
    _drop_index("ix_trading_signals_user_id", "trading_signals")
    op.drop_table("trading_signals")


def _create_observability_tables() -> None:
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
    _create_index("ix_audit_logs_action", "audit_logs", ["action"])
    _create_index("ix_audit_logs_exchange_account_id", "audit_logs", ["exchange_account_id"])
    _create_index("ix_audit_logs_severity", "audit_logs", ["severity"])
    _create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

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
    _create_index("ix_system_events_event_type", "system_events", ["event_type"])
    _create_index(
        "ix_system_events_exchange_account_id",
        "system_events",
        ["exchange_account_id"],
    )
    _create_index("ix_system_events_severity", "system_events", ["severity"])
    _create_index("ix_system_events_user_id", "system_events", ["user_id"])

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
    _create_index("ix_internal_notifications_channel", "internal_notifications", ["channel"])
    _create_index(
        "ix_internal_notifications_exchange_account_id",
        "internal_notifications",
        ["exchange_account_id"],
    )
    _create_index(
        "ix_internal_notifications_severity",
        "internal_notifications",
        ["severity"],
    )
    _create_index("ix_internal_notifications_user_id", "internal_notifications", ["user_id"])


def _drop_observability_tables() -> None:
    _drop_index("ix_internal_notifications_user_id", "internal_notifications")
    _drop_index("ix_internal_notifications_severity", "internal_notifications")
    _drop_index("ix_internal_notifications_exchange_account_id", "internal_notifications")
    _drop_index("ix_internal_notifications_channel", "internal_notifications")
    op.drop_table("internal_notifications")

    _drop_index("ix_system_events_user_id", "system_events")
    _drop_index("ix_system_events_severity", "system_events")
    _drop_index("ix_system_events_exchange_account_id", "system_events")
    _drop_index("ix_system_events_event_type", "system_events")
    op.drop_table("system_events")

    _drop_index("ix_audit_logs_user_id", "audit_logs")
    _drop_index("ix_audit_logs_severity", "audit_logs")
    _drop_index("ix_audit_logs_exchange_account_id", "audit_logs")
    _drop_index("ix_audit_logs_action", "audit_logs")
    op.drop_table("audit_logs")
