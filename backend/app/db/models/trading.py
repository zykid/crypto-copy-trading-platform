import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class SignalSource(StrEnum):
    MANUAL = "manual"
    COPY_TRADE = "copy_trade"
    AI = "ai"
    STRATEGY = "strategy"
    WEBHOOK = "webhook"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class RiskDecision(StrEnum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"


class OrderExecutionStatus(StrEnum):
    CREATED = "CREATED"
    RISK_PASSED = "RISK_PASSED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    source: Mapped[SignalSource] = mapped_column(Enum(SignalSource), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    target_position_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskSetting(Base):
    __tablename__ = "risk_settings"
    __table_args__ = (UniqueConstraint("exchange_account_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exchange_account_id: Mapped[str] = mapped_column(
        ForeignKey("exchange_accounts.id"), index=True, nullable=False
    )
    trading_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_single_order_notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    max_position_notional: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    max_leverage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    min_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    max_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    blocked_symbols: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (UniqueConstraint("exchange_account_id", "asset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exchange_account_id: Mapped[str] = mapped_column(
        ForeignKey("exchange_accounts.id"), index=True, nullable=False
    )
    asset: Mapped[str] = mapped_column(String(40), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 10), default=Decimal("0"), nullable=False
    )
    locked_quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 10), default=Decimal("0"), nullable=False
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 10), default=Decimal("0"), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("exchange_account_id", "symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exchange_account_id: Mapped[str] = mapped_column(
        ForeignKey("exchange_accounts.id"), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), default=Decimal("0"))
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrderExecution(Base):
    __tablename__ = "order_executions"
    __table_args__ = (UniqueConstraint("signal_id", "exchange_account_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    signal_id: Mapped[str] = mapped_column(ForeignKey("trading_signals.id"), index=True)
    execution_id: Mapped[str] = mapped_column(String(36), unique=True, default=new_uuid)
    exchange_account_id: Mapped[str] = mapped_column(ForeignKey("exchange_accounts.id"), index=True)
    exchange_name: Mapped[str] = mapped_column(String(40), nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    status: Mapped[OrderExecutionStatus] = mapped_column(Enum(OrderExecutionStatus), nullable=False)
    risk_result: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    exchange_response: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrderExecutionTransition(Base):
    __tablename__ = "order_execution_transitions"
    __table_args__ = (UniqueConstraint("order_execution_id", "sequence_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    order_execution_id: Mapped[str] = mapped_column(
        ForeignKey("order_executions.id"), index=True, nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
