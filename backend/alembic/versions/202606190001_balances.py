"""add balances table

Revision ID: 202606190001
Revises: 202606120001
Create Date: 2026-06-19 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606190001"
down_revision: str | None = "202606120001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "balances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("exchange_account_id", sa.String(length=36), nullable=False),
        sa.Column("asset", sa.String(length=40), nullable=False),
        sa.Column("available_quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("locked_quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("total_quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_account_id", "asset"),
    )
    op.create_index("ix_balances_user_id", "balances", ["user_id"])
    op.create_index(
        "ix_balances_exchange_account_id",
        "balances",
        ["exchange_account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_balances_exchange_account_id",
        table_name="balances",
    )
    op.drop_index("ix_balances_user_id", table_name="balances")
    op.drop_table("balances")
