from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    RiskDecision,
    SignalSource,
    TradingSignal,
)
from app.services.order_state_machine import (
    InvalidOrderStateTransitionError,
    record_initial_order_state,
    transition_order_execution,
)
from app.services.risk_engine import (
    RiskOrderInput,
    check_order_risk,
    get_or_create_risk_settings,
)
from app.services.testnet_order_execution import TestnetOrderExecutionResult

if TYPE_CHECKING:
    from app.services.testnet_order_api import TestnetOrderApiContext

_SENSITIVE_RESPONSE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api_secret",
        "apisecret",
        "passphrase",
        "authorization",
        "signature",
        "sign",
    }
)


class TestnetOrderIdempotencyConflictError(RuntimeError):
    pass


class TestnetOrderRiskRejectedError(RuntimeError):
    pass


class TestnetExchangeOrderRejectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class TestnetSubmissionRecord:
    execution: OrderExecution
    idempotent_replay: bool


def create_or_get_testnet_submission_execution(
    db: Session,
    *,
    user_id: str,
    context: "TestnetOrderApiContext",
) -> TestnetSubmissionRecord:
    existing = db.scalar(
        select(OrderExecution).where(
            OrderExecution.client_order_id == context.order.client_order_id
        )
    )
    if existing is not None:
        if (
            existing.user_id != user_id
            or existing.exchange_account_id != context.account.id
            or existing.exchange_name != context.account.exchange_name.value
        ):
            raise TestnetOrderIdempotencyConflictError("client order id is already in use")
        return TestnetSubmissionRecord(execution=existing, idempotent_replay=True)

    signal = TradingSignal(
        user_id=user_id,
        source=SignalSource.MANUAL,
        symbol=context.order.symbol.upper(),
        side=context.order.side,
        order_type=context.order.order_type,
        price=context.order.price,
        quantity=context.order.quantity,
        raw_payload={
            "source": "testnet_order_submit",
            "approval_audit_log_id": context.authorization.audit_log_id,
        },
    )
    db.add(signal)
    db.flush()

    execution = OrderExecution(
        user_id=user_id,
        signal_id=signal.id,
        exchange_account_id=context.account.id,
        exchange_name=context.account.exchange_name.value,
        client_order_id=context.order.client_order_id,
        symbol=context.order.symbol.upper(),
        side=context.order.side,
        order_type=context.order.order_type,
        price=context.order.price,
        quantity=context.order.quantity,
        status=OrderExecutionStatus.CREATED,
    )
    db.add(execution)
    db.flush()
    record_initial_order_state(db, execution=execution, reason="testnet_execution_created")

    settings = get_or_create_risk_settings(
        db,
        user_id=user_id,
        exchange_account_id=context.account.id,
    )
    risk_result = check_order_risk(
        account=context.account,
        settings=settings,
        order=RiskOrderInput(
            symbol=context.order.symbol.upper(),
            side=context.order.side,
            quantity=context.order.quantity,
            price=context.order.price,
        ),
        allow_non_simulation=True,
    )
    execution.risk_result = risk_result.to_dict()
    if risk_result.decision != RiskDecision.PASSED:
        execution.error_message = "; ".join(risk_result.reasons)
        transition_order_execution(
            db,
            execution=execution,
            to_status=OrderExecutionStatus.REJECTED,
            reason="testnet_risk_rejected",
        )
        db.commit()
        db.refresh(execution)
        raise TestnetOrderRiskRejectedError("testnet order risk checks rejected the request")

    transition_order_execution(
        db,
        execution=execution,
        to_status=OrderExecutionStatus.RISK_PASSED,
        reason="testnet_risk_passed",
    )
    transition_order_execution(
        db,
        execution=execution,
        to_status=OrderExecutionStatus.SUBMITTED,
        reason="testnet_order_submission_started",
    )
    db.commit()
    db.refresh(execution)
    return TestnetSubmissionRecord(execution=execution, idempotent_replay=False)


def record_testnet_submission_accepted(
    db: Session,
    *,
    execution: OrderExecution,
    result: TestnetOrderExecutionResult,
) -> OrderExecution:
    response = _safe_exchange_response(result.exchange_response)
    _raise_for_exchange_rejection(execution.exchange_name, response)
    if execution.status != OrderExecutionStatus.SUBMITTED:
        raise InvalidOrderStateTransitionError(
            "testnet execution is not awaiting exchange acceptance"
        )
    execution.exchange_response = response
    exchange_order_id = _exchange_order_id(execution.exchange_name, response)
    if exchange_order_id:
        execution.exchange_order_id = exchange_order_id
    transition_order_execution(
        db,
        execution=execution,
        to_status=OrderExecutionStatus.ACCEPTED,
        reason="testnet_exchange_accepted",
        details={"exchange": execution.exchange_name},
    )
    db.commit()
    db.refresh(execution)
    return execution


def record_testnet_submission_failure(
    db: Session,
    *,
    execution: OrderExecution,
    failure_type: str,
) -> OrderExecution:
    if execution.status != OrderExecutionStatus.SUBMITTED:
        return execution
    execution.error_message = "testnet exchange request failed"
    transition_order_execution(
        db,
        execution=execution,
        to_status=OrderExecutionStatus.FAILED,
        reason="testnet_exchange_request_failed",
        details={"failure_type": failure_type},
    )
    db.commit()
    db.refresh(execution)
    return execution


def _raise_for_exchange_rejection(exchange_name: str, response: dict[str, object]) -> None:
    if exchange_name == "bybit" and response.get("retCode") not in (None, 0, "0"):
        raise TestnetExchangeOrderRejectedError("Bybit rejected the testnet order")
    if exchange_name == "okx" and response.get("code") not in (None, "0", 0):
        raise TestnetExchangeOrderRejectedError("OKX rejected the testnet order")
    if exchange_name == "binance" and response.get("code") not in (None, 0, "0"):
        raise TestnetExchangeOrderRejectedError("Binance rejected the testnet order")


def _exchange_order_id(exchange_name: str, response: dict[str, object]) -> str | None:
    if exchange_name == "binance":
        return _optional_text(response.get("orderId"))
    if exchange_name == "bybit":
        return _optional_text(_mapping(response.get("result")).get("orderId"))
    if exchange_name == "okx":
        rows = response.get("data")
        if isinstance(rows, list) and rows:
            return _optional_text(_mapping(rows[0]).get("ordId"))
    return None


def _safe_exchange_response(value: dict[str, Any]) -> dict[str, object]:
    return _safe_value(value)


def _safe_value(value: Any) -> object:
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key).replace("-", "_").lower() not in _SENSITIVE_RESPONSE_KEYS
        }
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
