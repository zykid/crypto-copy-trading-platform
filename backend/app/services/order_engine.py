from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import ExchangeAccount
from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderSide,
    RiskDecision,
    TradingSignal,
)
from app.exchanges.mock import MockExchange
from app.services.emergency_stop import assert_new_orders_allowed
from app.services.position_engine import apply_fill, calculate_delta, get_or_create_position
from app.services.risk_engine import RiskOrderInput, check_order_risk, get_or_create_risk_settings


class OrderFailureAlertRuntime(Protocol):
    def notify_order_failure(
        self,
        *,
        status: str,
        failure_type: str,
    ) -> tuple[object, ...]: ...


def execute_signal_for_account(
    db: Session,
    *,
    user_id: str,
    signal_id: str,
    exchange_account_id: str,
    exchange: MockExchange | None = None,
    alert_runtime: OrderFailureAlertRuntime | None = None,
) -> OrderExecution:
    assert_new_orders_allowed(db)
    signal = _get_owned_signal(db, user_id=user_id, signal_id=signal_id)
    account = _get_owned_account(db, user_id=user_id, exchange_account_id=exchange_account_id)

    existing = db.scalar(
        select(OrderExecution).where(
            OrderExecution.signal_id == signal.id,
            OrderExecution.exchange_account_id == account.id,
        )
    )
    if existing is not None:
        return existing

    side, quantity = _resolve_side_and_quantity(db, signal=signal, account=account)
    client_order_id = f"sig-{signal.id[:8]}-acct-{account.id[:8]}"
    execution = OrderExecution(
        user_id=user_id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name.value,
        client_order_id=client_order_id,
        symbol=signal.symbol,
        side=side,
        order_type=signal.order_type,
        price=signal.price,
        quantity=quantity,
        status=OrderExecutionStatus.CREATED,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    risk_settings = get_or_create_risk_settings(
        db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
    )
    risk_result = check_order_risk(
        account=account,
        settings=risk_settings,
        order=RiskOrderInput(
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            price=signal.price,
        ),
    )
    execution.risk_result = risk_result.to_dict()
    if risk_result.decision != RiskDecision.PASSED or quantity <= 0:
        execution.status = OrderExecutionStatus.FAILED
        execution.error_message = "; ".join(risk_result.reasons) or "zero quantity order"
        db.commit()
        db.refresh(execution)
        _notify_order_failure(
            alert_runtime,
            status=execution.status,
            failure_type=(
                "risk_rejected"
                if risk_result.decision != RiskDecision.PASSED
                else "unknown"
            ),
        )
        return execution

    execution.status = OrderExecutionStatus.RISK_PASSED
    db.commit()
    adapter = exchange or MockExchange()
    execution.status = OrderExecutionStatus.SUBMITTED
    response = adapter.place_order(
        client_order_id=client_order_id,
        symbol=signal.symbol,
        side=side,
        order_type=signal.order_type,
        quantity=quantity,
        price=signal.price,
    )
    execution.exchange_order_id = str(response["exchange_order_id"])
    execution.exchange_response = response
    execution.status = OrderExecutionStatus.FILLED
    apply_fill(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        symbol=signal.symbol,
        side=side,
        quantity=quantity,
    )
    db.commit()
    db.refresh(execution)
    return execution


def _get_owned_signal(db: Session, *, user_id: str, signal_id: str) -> TradingSignal:
    signal = db.scalar(
        select(TradingSignal).where(TradingSignal.id == signal_id, TradingSignal.user_id == user_id)
    )
    if signal is None:
        raise ValueError("signal not found")
    return signal


def _get_owned_account(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
) -> ExchangeAccount:
    account = db.scalar(
        select(ExchangeAccount).where(
            ExchangeAccount.id == exchange_account_id,
            ExchangeAccount.user_id == user_id,
        )
    )
    if account is None:
        raise ValueError("exchange account not found")
    return account


def _resolve_side_and_quantity(
    db: Session,
    *,
    signal: TradingSignal,
    account: ExchangeAccount,
) -> tuple[OrderSide, Decimal]:
    if signal.target_position_quantity is None:
        if signal.quantity is None:
            raise ValueError("signal quantity is required")
        return signal.side, signal.quantity
    position = get_or_create_position(
        db,
        user_id=signal.user_id,
        exchange_account_id=account.id,
        symbol=signal.symbol,
    )
    delta = calculate_delta(
        symbol=signal.symbol,
        current_quantity=position.quantity,
        target_quantity=signal.target_position_quantity,
    )
    return delta.side or signal.side, delta.delta_quantity


def _notify_order_failure(
    alert_runtime: OrderFailureAlertRuntime | None,
    *,
    status: OrderExecutionStatus,
    failure_type: str,
) -> None:
    if alert_runtime is None:
        return
    alert_runtime.notify_order_failure(
        status=status.value,
        failure_type=failure_type,
    )
