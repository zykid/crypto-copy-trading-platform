from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderExecutionTransition,
)

TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderExecutionStatus.FILLED,
        OrderExecutionStatus.CANCELLED,
        OrderExecutionStatus.REJECTED,
        OrderExecutionStatus.FAILED,
        OrderExecutionStatus.TIMEOUT,
    }
)

ALLOWED_ORDER_TRANSITIONS: dict[
    OrderExecutionStatus,
    frozenset[OrderExecutionStatus],
] = {
    OrderExecutionStatus.CREATED: frozenset(
        {
            OrderExecutionStatus.RISK_PASSED,
            OrderExecutionStatus.REJECTED,
            OrderExecutionStatus.FAILED,
        }
    ),
    OrderExecutionStatus.RISK_PASSED: frozenset(
        {OrderExecutionStatus.SUBMITTED, OrderExecutionStatus.FAILED}
    ),
    OrderExecutionStatus.SUBMITTED: frozenset(
        {
            OrderExecutionStatus.ACCEPTED,
            OrderExecutionStatus.PARTIALLY_FILLED,
            OrderExecutionStatus.FILLED,
            OrderExecutionStatus.CANCELLED,
            OrderExecutionStatus.REJECTED,
            OrderExecutionStatus.FAILED,
            OrderExecutionStatus.TIMEOUT,
        }
    ),
    OrderExecutionStatus.ACCEPTED: frozenset(
        {
            OrderExecutionStatus.PARTIALLY_FILLED,
            OrderExecutionStatus.FILLED,
            OrderExecutionStatus.CANCELLED,
            OrderExecutionStatus.REJECTED,
            OrderExecutionStatus.FAILED,
            OrderExecutionStatus.TIMEOUT,
        }
    ),
    OrderExecutionStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderExecutionStatus.PARTIALLY_FILLED,
            OrderExecutionStatus.FILLED,
            OrderExecutionStatus.CANCELLED,
            OrderExecutionStatus.FAILED,
            OrderExecutionStatus.TIMEOUT,
        }
    ),
}


class InvalidOrderStateTransitionError(RuntimeError):
    pass


def record_initial_order_state(
    db: Session,
    *,
    execution: OrderExecution,
    reason: str = "execution_created",
) -> OrderExecutionTransition:
    if execution.status != OrderExecutionStatus.CREATED:
        raise InvalidOrderStateTransitionError("initial order state must be CREATED")
    return _add_transition(
        db,
        execution=execution,
        from_status=None,
        to_status=OrderExecutionStatus.CREATED,
        reason=reason,
    )


def transition_order_execution(
    db: Session,
    *,
    execution: OrderExecution,
    to_status: OrderExecutionStatus,
    reason: str,
    details: dict[str, object] | None = None,
) -> OrderExecutionTransition:
    from_status = OrderExecutionStatus(execution.status)
    allowed = ALLOWED_ORDER_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise InvalidOrderStateTransitionError(
            f"order status transition {from_status.value} -> {to_status.value} is not allowed"
        )
    execution.status = to_status
    return _add_transition(
        db,
        execution=execution,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        details=details,
    )


def _add_transition(
    db: Session,
    *,
    execution: OrderExecution,
    from_status: OrderExecutionStatus | None,
    to_status: OrderExecutionStatus,
    reason: str,
    details: dict[str, object] | None = None,
) -> OrderExecutionTransition:
    if not execution.id:
        raise InvalidOrderStateTransitionError("order execution must be persisted first")
    transition = OrderExecutionTransition(
        user_id=execution.user_id,
        order_execution_id=execution.id,
        sequence_number=_next_sequence_number(db, execution.id),
        from_status=from_status.value if from_status else None,
        to_status=to_status.value,
        reason=reason,
        details=details,
    )
    db.add(transition)
    return transition


def _next_sequence_number(db: Session, order_execution_id: str) -> int:
    persisted_max = db.scalar(
        select(func.max(OrderExecutionTransition.sequence_number)).where(
            OrderExecutionTransition.order_execution_id == order_execution_id
        )
    ) or 0
    pending_max = max(
        (
            transition.sequence_number
            for transition in db.new
            if isinstance(transition, OrderExecutionTransition)
            and transition.order_execution_id == order_execution_id
        ),
        default=0,
    )
    return max(persisted_max, pending_max) + 1
