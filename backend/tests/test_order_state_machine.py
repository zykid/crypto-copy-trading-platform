from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderSide,
    OrderType,
)
from app.services.order_state_machine import (
    InvalidOrderStateTransitionError,
    record_initial_order_state,
    transition_order_execution,
)


def _execution(status: OrderExecutionStatus = OrderExecutionStatus.CREATED) -> OrderExecution:
    return OrderExecution(
        id="execution-row-id",
        user_id="user-id",
        signal_id="signal-id",
        execution_id="execution-id",
        exchange_account_id="account-id",
        exchange_name="mock",
        client_order_id="client-order-id",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        status=status,
    )


def test_order_state_machine_records_valid_lifecycle(db_session: Session) -> None:
    execution = _execution()

    initial = record_initial_order_state(db_session, execution=execution)
    risk_passed = transition_order_execution(
        db_session,
        execution=execution,
        to_status=OrderExecutionStatus.RISK_PASSED,
        reason="risk_passed",
    )
    submitted = transition_order_execution(
        db_session,
        execution=execution,
        to_status=OrderExecutionStatus.SUBMITTED,
        reason="submitted",
    )
    filled = transition_order_execution(
        db_session,
        execution=execution,
        to_status=OrderExecutionStatus.FILLED,
        reason="filled",
    )

    assert initial.from_status is None
    assert [
        initial.sequence_number,
        risk_passed.sequence_number,
        submitted.sequence_number,
        filled.sequence_number,
    ] == [1, 2, 3, 4]
    assert risk_passed.from_status == "CREATED"
    assert submitted.from_status == "RISK_PASSED"
    assert filled.from_status == "SUBMITTED"
    assert execution.status == OrderExecutionStatus.FILLED


def test_order_state_machine_rejects_skipped_and_terminal_transitions(
    db_session: Session,
) -> None:
    execution = _execution()

    with pytest.raises(InvalidOrderStateTransitionError, match="CREATED -> FILLED"):
        transition_order_execution(
            db_session,
            execution=execution,
            to_status=OrderExecutionStatus.FILLED,
            reason="invalid_skip",
        )

    execution.status = OrderExecutionStatus.FILLED
    with pytest.raises(InvalidOrderStateTransitionError, match="FILLED -> CANCELLED"):
        transition_order_execution(
            db_session,
            execution=execution,
            to_status=OrderExecutionStatus.CANCELLED,
            reason="invalid_terminal_change",
        )
