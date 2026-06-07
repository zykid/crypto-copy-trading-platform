"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-07 18:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "exchange_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("exchange_name", sa.String(length=40), nullable=False),
        sa.Column("account_mode", sa.String(length=20), nullable=False),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_accounts_user_id", "exchange_accounts", ["user_id"])

    op.create_table(
        "api_key_secrets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "exchange_account_id",
            sa.String(length=36),
            sa.ForeignKey("exchange_accounts.id"),
            nullable=False,
        ),
        sa.Column("encrypted_api_key", sa.String(length=512), nullable=False),
        sa.Column("encrypted_api_secret", sa.String(length=512), nullable=False),
        sa.Column("encrypted_passphrase", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("exchange_account_id"),
    )
    op.create_index("ix_api_key_secrets_user_id", "api_key_secrets", ["user_id"])
    op.create_index(
        "ix_api_key_secrets_exchange_account_id",
        "api_key_secrets",
        ["exchange_account_id"],
    )

    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "grantee_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("view_only", sa.Boolean(), nullable=False),
        sa.Column("copy_follow", sa.Boolean(), nullable=False),
        sa.Column("pause_follow", sa.Boolean(), nullable=False),
        sa.Column("edit_copy_rule", sa.Boolean(), nullable=False),
        sa.Column("trade_manual", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_user_id", "grantee_user_id"),
    )
    op.create_index(
        "ix_user_permissions_owner_user_id",
        "user_permissions",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_user_permissions_grantee_user_id",
        "user_permissions",
        ["grantee_user_id"],
    )

    op.create_table(
        "trading_signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("target_position_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trading_signals_user_id", "trading_signals", ["user_id"])

    op.create_table(
        "risk_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "exchange_account_id",
            sa.String(length=36),
            sa.ForeignKey("exchange_accounts.id"),
            nullable=False,
        ),
        sa.Column("trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("max_single_order_notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_position_notional", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_leverage", sa.Numeric(12, 4), nullable=True),
        sa.Column("min_order_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("max_order_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("blocked_symbols", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("exchange_account_id"),
    )
    op.create_index("ix_risk_settings_user_id", "risk_settings", ["user_id"])
    op.create_index(
        "ix_risk_settings_exchange_account_id",
        "risk_settings",
        ["exchange_account_id"],
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "exchange_account_id",
            sa.String(length=36),
            sa.ForeignKey("exchange_accounts.id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("exchange_account_id", "symbol"),
    )
    op.create_index("ix_positions_user_id", "positions", ["user_id"])
    op.create_index("ix_positions_exchange_account_id", "positions", ["exchange_account_id"])

    op.create_table(
        "order_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "signal_id",
            sa.String(length=36),
            sa.ForeignKey("trading_signals.id"),
            nullable=True,
        ),
        sa.Column("execution_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column(
            "exchange_account_id",
            sa.String(length=36),
            sa.ForeignKey("exchange_accounts.id"),
            nullable=True,
        ),
        sa.Column("exchange_name", sa.String(length=40), nullable=False),
        sa.Column("client_order_id", sa.String(length=80), nullable=False, unique=True),
        sa.Column("exchange_order_id", sa.String(length=120), nullable=True),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_result", sa.JSON(), nullable=True),
        sa.Column("exchange_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("signal_id", "exchange_account_id"),
    )
    op.create_index("ix_order_executions_user_id", "order_executions", ["user_id"])
    op.create_index("ix_order_executions_signal_id", "order_executions", ["signal_id"])
    op.create_index(
        "ix_order_executions_exchange_account_id",
        "order_executions",
        ["exchange_account_id"],
    )


def downgrade() -> None:
    op.drop_table("order_executions")
    op.drop_table("positions")
    op.drop_table("risk_settings")
    op.drop_table("trading_signals")
    op.drop_table("user_permissions")
    op.drop_table("api_key_secrets")
    op.drop_table("exchange_accounts")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
