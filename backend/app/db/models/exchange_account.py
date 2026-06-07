from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.user import new_uuid


class ExchangeName(StrEnum):
    BINANCE = "binance"
    OKX = "okx"
    BYBIT = "bybit"
    MOCK = "mock"


class AccountMode(StrEnum):
    SIMULATION = "SIMULATION"
    TESTNET = "TESTNET"
    REAL = "REAL"


class ExchangeAccount(Base):
    __tablename__ = "exchange_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exchange_name: Mapped[ExchangeName] = mapped_column(Enum(ExchangeName), nullable=False)
    account_mode: Mapped[AccountMode] = mapped_column(
        Enum(AccountMode), default=AccountMode.SIMULATION, nullable=False
    )
    account_label: Mapped[str] = mapped_column(String(120), nullable=False)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApiKeySecret(Base):
    __tablename__ = "api_key_secrets"
    __table_args__ = (UniqueConstraint("exchange_account_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exchange_account_id: Mapped[str] = mapped_column(
        ForeignKey("exchange_accounts.id"), index=True, nullable=False
    )
    encrypted_api_key: Mapped[str] = mapped_column(String(512), nullable=False)
    encrypted_api_secret: Mapped[str] = mapped_column(String(512), nullable=False)
    encrypted_passphrase: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
