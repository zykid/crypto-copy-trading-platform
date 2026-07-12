from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderExecutionTransition,
    OrderSide,
    OrderType,
    SignalSource,
    TradingSignal,
)
from app.services.exchange_accounts import create_account
from app.services.order_state_machine import (
    record_initial_order_state,
    transition_order_execution,
)
from app.services.testnet_order_lifecycle import (
    TestnetOrderEventValidationError as OrderEventValidationError,
)
from app.services.testnet_order_lifecycle import (
    TestnetOrderLifecycleProcessor as OrderLifecycleProcessor,
)
from app.services.testnet_order_lifecycle import (
    normalize_testnet_rest_order_status,
    normalize_testnet_user_stream_order_event,
)
from app.services.testnet_user_stream_runtime import parse_testnet_user_stream_event
from app.services.users import create_user


@pytest.mark.parametrize(
    ("exchange_name", "payload", "expected_status", "client_order_id"),
    [
        (
            ExchangeName.BINANCE,
            {"e": "executionReport", "c": "client-1", "i": 101, "X": "FILLED"},
            OrderExecutionStatus.FILLED,
            "client-1",
        ),
        (
            ExchangeName.BYBIT,
            {
                "topic": "order",
                "data": [
                    {
                        "orderLinkId": "client-2",
                        "orderId": "202",
                        "orderStatus": "PartiallyFilled",
                    }
                ],
            },
            OrderExecutionStatus.PARTIALLY_FILLED,
            "client-2",
        ),
        (
            ExchangeName.OKX,
            {
                "arg": {"channel": "orders"},
                "data": [{"clOrdId": "client-3", "ordId": "303", "state": "canceled"}],
            },
            OrderExecutionStatus.CANCELLED,
            "client-3",
        ),
    ],
)
def test_normalize_testnet_order_events(
    exchange_name: ExchangeName,
    payload: dict[str, object],
    expected_status: OrderExecutionStatus,
    client_order_id: str,
) -> None:
    event = normalize_testnet_user_stream_order_event(
        exchange_name=exchange_name,
        payload=payload,
    )

    assert event.status == expected_status
    assert event.client_order_id == client_order_id


def test_testnet_order_lifecycle_applies_deduplicates_and_ignores_stale_events(
    db_session: Session,
) -> None:
    user_id, account_id, execution = _submitted_execution(db_session)
    processor = OrderLifecycleProcessor(
        db=db_session,
        user_id=user_id,
        exchange_account_id=account_id,
    )

    accepted_event = parse_testnet_user_stream_event(
        exchange_name=ExchangeName.BINANCE,
        payload={
            "e": "executionReport",
            "c": execution.client_order_id,
            "i": 9001,
            "X": "NEW",
            "E": 1700000000000,
            "z": "0",
            "apiSecret": "must-not-be-persisted",
        },
    )
    accepted = processor.handle_user_stream_event(accepted_event)
    duplicate = processor.handle_user_stream_event(accepted_event)
    filled = processor.handle_user_stream_event(
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BINANCE,
            payload={
                "e": "executionReport",
                "c": execution.client_order_id,
                "i": 9001,
                "X": "FILLED",
                "E": 1700000000100,
                "z": "0.01",
            },
        )
    )
    stale = processor.handle_user_stream_event(accepted_event)

    assert accepted.transitioned is True
    assert duplicate.duplicate is True
    assert filled.status == OrderExecutionStatus.FILLED
    assert stale.ignored is True
    transitions = db_session.scalars(
        select(OrderExecutionTransition)
        .where(OrderExecutionTransition.order_execution_id == execution.id)
        .order_by(OrderExecutionTransition.sequence_number)
    ).all()
    assert [item.to_status for item in transitions] == [
        "CREATED",
        "RISK_PASSED",
        "SUBMITTED",
        "ACCEPTED",
        "FILLED",
    ]
    assert "must-not-be-persisted" not in str([item.details for item in transitions])


def test_testnet_order_lifecycle_does_not_cross_tenant_boundary(
    db_session: Session,
) -> None:
    _, account_id, execution = _submitted_execution(db_session)
    other = create_user(
        db_session,
        email="other-lifecycle@example.com",
        username="other_lifecycle",
        password="SafePassword123!",
    )
    processor = OrderLifecycleProcessor(
        db=db_session,
        user_id=other.id,
        exchange_account_id=account_id,
    )
    result = processor.handle_user_stream_event(
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BINANCE,
            payload={
                "e": "executionReport",
                "c": execution.client_order_id,
                "i": 9001,
                "X": "FILLED",
            },
        )
    )

    assert result.matched is False
    assert result.reason == "owned_order_execution_not_found"


def test_testnet_order_event_rejects_unknown_status() -> None:
    with pytest.raises(OrderEventValidationError, match="unsupported"):
        normalize_testnet_user_stream_order_event(
            exchange_name=ExchangeName.BINANCE,
            payload={"e": "executionReport", "c": "client-1", "X": "UNKNOWN"},
        )


def test_testnet_order_event_rejects_invalid_filled_quantity() -> None:
    with pytest.raises(OrderEventValidationError, match="invalid filled quantity"):
        normalize_testnet_user_stream_order_event(
            exchange_name=ExchangeName.BINANCE,
            payload={
                "e": "executionReport",
                "c": "client-1",
                "X": "FILLED",
                "z": {"unexpected": "value"},
            },
        )


@pytest.mark.parametrize(
    ("exchange_name", "payload", "expected_status", "client_order_id"),
    [
        (
            ExchangeName.BINANCE,
            {
                "clientOrderId": "rest-client-1",
                "orderId": 1,
                "status": "FILLED",
                "executedQty": "0.01",
            },
            OrderExecutionStatus.FILLED,
            "rest-client-1",
        ),
        (
            ExchangeName.BYBIT,
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "orderLinkId": "rest-client-2",
                            "orderId": "2",
                            "orderStatus": "New",
                            "cumExecQty": "0",
                        }
                    ]
                },
            },
            OrderExecutionStatus.ACCEPTED,
            "rest-client-2",
        ),
        (
            ExchangeName.OKX,
            {
                "code": "0",
                "data": [
                    {
                        "clOrdId": "rest-client-3",
                        "ordId": "3",
                        "state": "partially_filled",
                        "accFillSz": "0.01",
                    }
                ],
            },
            OrderExecutionStatus.PARTIALLY_FILLED,
            "rest-client-3",
        ),
    ],
)
def test_normalize_testnet_rest_order_statuses(
    exchange_name: ExchangeName,
    payload: dict[str, object],
    expected_status: OrderExecutionStatus,
    client_order_id: str,
) -> None:
    event = normalize_testnet_rest_order_status(
        exchange_name=exchange_name,
        payload=payload,
    )

    assert event.status == expected_status
    assert event.client_order_id == client_order_id


def _submitted_execution(
    db_session: Session,
) -> tuple[str, str, OrderExecution]:
    owner = create_user(
        db_session,
        email="lifecycle@example.com",
        username="lifecycle_user",
        password="SafePassword123!",
    )
    account = create_account(
        db_session,
        user_id=owner.id,
        data={
            "exchange_name": ExchangeName.BINANCE,
            "account_mode": AccountMode.TESTNET,
            "account_label": "Binance lifecycle test",
        },
    )
    signal = TradingSignal(
        user_id=owner.id,
        source=SignalSource.MANUAL,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        raw_payload={"source": SignalSource.MANUAL.value},
    )
    db_session.add(signal)
    db_session.flush()
    execution = OrderExecution(
        user_id=owner.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange_name=ExchangeName.BINANCE.value,
        client_order_id="testnet-lifecycle-client",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        status=OrderExecutionStatus.CREATED,
    )
    db_session.add(execution)
    db_session.flush()
    record_initial_order_state(db_session, execution=execution)
    transition_order_execution(
        db_session,
        execution=execution,
        to_status=OrderExecutionStatus.RISK_PASSED,
        reason="testnet_gate_passed",
    )
    transition_order_execution(
        db_session,
        execution=execution,
        to_status=OrderExecutionStatus.SUBMITTED,
        reason="testnet_order_submitted",
    )
    db_session.commit()
    db_session.refresh(execution)
    return owner.id, account.id, execution
