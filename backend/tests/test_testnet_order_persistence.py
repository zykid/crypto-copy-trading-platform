from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeAccount, ExchangeName
from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderExecutionTransition,
    OrderSide,
    OrderType,
    RiskSetting,
)
from app.db.models.user import User
from app.exchanges.http_client import ExchangeCredentials
from app.services.testnet_order_api import TestnetOrderApiContext as OrderApiContext
from app.services.testnet_order_execution import TestnetOrderExecutionResult as OrderExecutionResult
from app.services.testnet_order_gate import check_testnet_order_gate
from app.services.testnet_order_persistence import (
    TestnetExchangeOrderRejectedError as ExchangeOrderRejectedError,
)
from app.services.testnet_order_persistence import (
    TestnetOrderIdempotencyConflictError as OrderIdempotencyConflictError,
)
from app.services.testnet_order_persistence import (
    TestnetOrderRiskRejectedError as OrderRiskRejectedError,
)
from app.services.testnet_order_persistence import (
    create_or_get_testnet_submission_execution,
    record_testnet_submission_accepted,
    record_testnet_submission_failure,
)
from app.services.testnet_order_request import TestnetOrderRequestInput as OrderRequestInput
from app.services.testnet_order_window_approval import (
    TestnetOrderWindowAuthorization as OrderWindowAuthorization,
)


def test_creates_submitted_execution_with_append_only_history(db_session: Session) -> None:
    owner, context = _context(db_session)

    record = create_or_get_testnet_submission_execution(
        db_session,
        user_id=owner.id,
        context=context,
    )

    assert record.idempotent_replay is False
    assert record.execution.status == OrderExecutionStatus.SUBMITTED
    assert record.execution.risk_result == {"decision": "PASSED", "reasons": []}
    transitions = db_session.scalars(
        select(OrderExecutionTransition)
        .where(OrderExecutionTransition.order_execution_id == record.execution.id)
        .order_by(OrderExecutionTransition.sequence_number)
    ).all()
    assert [transition.to_status for transition in transitions] == [
        "CREATED",
        "RISK_PASSED",
        "SUBMITTED",
    ]
    assert "test-api-secret" not in str(record.execution.risk_result)


def test_same_client_order_id_is_an_idempotent_replay(db_session: Session) -> None:
    owner, context = _context(db_session)
    created = create_or_get_testnet_submission_execution(
        db_session,
        user_id=owner.id,
        context=context,
    )

    replay = create_or_get_testnet_submission_execution(
        db_session,
        user_id=owner.id,
        context=context,
    )

    assert replay.idempotent_replay is True
    assert replay.execution.id == created.execution.id


def test_client_order_id_cannot_cross_tenant_boundary(db_session: Session) -> None:
    owner, context = _context(db_session)
    create_or_get_testnet_submission_execution(db_session, user_id=owner.id, context=context)
    other = User(email="other@example.com", username="other", password_hash="hashed")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(OrderIdempotencyConflictError):
        create_or_get_testnet_submission_execution(
            db_session,
            user_id=other.id,
            context=context,
        )


def test_risk_rejection_is_persisted_without_submitting(db_session: Session) -> None:
    owner, context = _context(db_session, blocked_symbols=["BTCUSDT"])

    with pytest.raises(OrderRiskRejectedError):
        create_or_get_testnet_submission_execution(
            db_session,
            user_id=owner.id,
            context=context,
        )

    rejected = db_session.scalar(select(OrderExecution).where(OrderExecution.user_id == owner.id))
    assert rejected is not None
    assert rejected.status == OrderExecutionStatus.REJECTED
    assert "symbol is blocked" in (rejected.error_message or "")


def test_exchange_acceptance_persists_safe_response_and_order_id(db_session: Session) -> None:
    owner, context = _context(db_session)
    record = create_or_get_testnet_submission_execution(
        db_session,
        user_id=owner.id,
        context=context,
    )

    accepted = record_testnet_submission_accepted(
        db_session,
        execution=record.execution,
        result=OrderExecutionResult(
            exchange_name=ExchangeName.BINANCE,
            client_order_id=context.order.client_order_id,
            request_method="POST",
            request_path="/api/v3/order",
            exchange_response={
                "orderId": "exchange-order-1",
                "clientOrderId": context.order.client_order_id,
                "api_secret": "must-not-persist",
            },
        ),
    )

    assert accepted.status == OrderExecutionStatus.ACCEPTED
    assert accepted.exchange_order_id == "exchange-order-1"
    assert "must-not-persist" not in str(accepted.exchange_response)


def test_exchange_rejection_can_be_recorded_as_failed(db_session: Session) -> None:
    owner, context = _context(db_session, exchange_name=ExchangeName.BYBIT)
    record = create_or_get_testnet_submission_execution(
        db_session,
        user_id=owner.id,
        context=context,
    )

    with pytest.raises(ExchangeOrderRejectedError):
        record_testnet_submission_accepted(
            db_session,
            execution=record.execution,
            result=OrderExecutionResult(
                exchange_name=ExchangeName.BYBIT,
                client_order_id=context.order.client_order_id,
                request_method="POST",
                request_path="/v5/order/create",
                exchange_response={"retCode": 10001, "retMsg": "rejected"},
            ),
        )

    failed = record_testnet_submission_failure(
        db_session,
        execution=record.execution,
        failure_type="exchange_rejected",
    )
    assert failed.status == OrderExecutionStatus.FAILED
    assert failed.error_message == "testnet exchange request failed"


def _context(
    db_session: Session,
    *,
    exchange_name: ExchangeName = ExchangeName.BINANCE,
    blocked_symbols: list[str] | None = None,
) -> tuple[User, OrderApiContext]:
    owner = User(email="owner@example.com", username="owner", password_hash="hashed")
    db_session.add(owner)
    db_session.flush()
    account = ExchangeAccount(
        user_id=owner.id,
        exchange_name=exchange_name,
        account_mode=AccountMode.TESTNET,
        account_label="testnet account",
        trading_enabled=True,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(
        RiskSetting(
            user_id=owner.id,
            exchange_account_id=account.id,
            trading_enabled=True,
            blocked_symbols=blocked_symbols or [],
            max_single_order_notional=Decimal("100"),
        )
    )
    db_session.commit()
    db_session.refresh(account)
    order = OrderRequestInput(
        exchange_name=exchange_name,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.001"),
        price=Decimal("100"),
        client_order_id="testnet-persistence-client",
    )
    gate = check_testnet_order_gate(
        exchange_name=exchange_name,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )
    return owner, OrderApiContext(
        account=account,
        order=order,
        gate_result=gate,
        credentials=ExchangeCredentials(
            api_key="test-api-key",
            api_secret="test-api-secret",
            passphrase="test-passphrase",
        ),
        authorization=OrderWindowAuthorization(
            audit_log_id="approval-audit-1",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        ),
    )
