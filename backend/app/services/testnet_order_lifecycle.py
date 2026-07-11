from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import OrderExecution, OrderExecutionStatus
from app.services.order_state_machine import (
    InvalidOrderStateTransitionError,
    transition_order_execution,
)
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEvent,
    TestnetUserStreamEventType,
)


@dataclass(frozen=True)
class NormalizedTestnetOrderEvent:
    exchange_name: ExchangeName
    client_order_id: str | None
    exchange_order_id: str | None
    status: OrderExecutionStatus
    event_id: str | None = None
    filled_quantity: Decimal | None = None


@dataclass(frozen=True)
class TestnetOrderLifecycleResult:
    matched: bool
    transitioned: bool
    duplicate: bool
    ignored: bool
    execution_id: str | None
    status: OrderExecutionStatus | None
    reason: str


class TestnetOrderEventValidationError(ValueError):
    pass


class TestnetOrderLifecycleProcessor:
    def __init__(
        self,
        *,
        db: Session,
        user_id: str,
        exchange_account_id: str,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._exchange_account_id = exchange_account_id

    def handle_user_stream_event(
        self,
        event: TestnetUserStreamEvent,
    ) -> TestnetOrderLifecycleResult:
        if event.event_type != TestnetUserStreamEventType.ORDER:
            return _ignored_result("non_order_event")
        normalized = normalize_testnet_user_stream_order_event(
            exchange_name=event.exchange_name,
            payload=event.raw_payload,
        )
        return self.apply(normalized)

    def apply(
        self,
        event: NormalizedTestnetOrderEvent,
    ) -> TestnetOrderLifecycleResult:
        execution = self._find_execution(event)
        if execution is None:
            return TestnetOrderLifecycleResult(
                matched=False,
                transitioned=False,
                duplicate=False,
                ignored=True,
                execution_id=None,
                status=None,
                reason="owned_order_execution_not_found",
            )

        current_status = OrderExecutionStatus(execution.status)
        if current_status == event.status:
            return _execution_result(
                execution,
                duplicate=True,
                ignored=True,
                reason="duplicate_order_event",
            )

        try:
            transition_order_execution(
                self._db,
                execution=execution,
                to_status=event.status,
                reason="testnet_user_stream_event",
                details=_safe_transition_details(event),
            )
        except InvalidOrderStateTransitionError:
            return _execution_result(
                execution,
                ignored=True,
                reason="stale_or_invalid_order_event",
            )

        if event.exchange_order_id and not execution.exchange_order_id:
            execution.exchange_order_id = event.exchange_order_id

        self._db.commit()
        self._db.refresh(execution)
        return _execution_result(
            execution,
            transitioned=True,
            reason="order_status_transitioned",
        )

    def _find_execution(
        self,
        event: NormalizedTestnetOrderEvent,
    ) -> OrderExecution | None:
        identifiers = []
        if event.client_order_id:
            identifiers.append(OrderExecution.client_order_id == event.client_order_id)
        if event.exchange_order_id:
            identifiers.append(OrderExecution.exchange_order_id == event.exchange_order_id)
        if not identifiers:
            raise TestnetOrderEventValidationError("order event has no usable identifier")
        return self._db.scalar(
            select(OrderExecution).where(
                OrderExecution.user_id == self._user_id,
                OrderExecution.exchange_account_id == self._exchange_account_id,
                OrderExecution.exchange_name == event.exchange_name.value,
                or_(*identifiers),
            )
        )


def normalize_testnet_user_stream_order_event(
    *,
    exchange_name: ExchangeName,
    payload: dict[str, Any],
) -> NormalizedTestnetOrderEvent:
    if exchange_name == ExchangeName.BINANCE:
        return _normalize_binance(payload)
    if exchange_name == ExchangeName.BYBIT:
        return _normalize_bybit(payload)
    if exchange_name == ExchangeName.OKX:
        return _normalize_okx(payload)
    raise TestnetOrderEventValidationError("unsupported testnet order event exchange")


def _normalize_binance(payload: dict[str, Any]) -> NormalizedTestnetOrderEvent:
    if payload.get("e") != "executionReport":
        raise TestnetOrderEventValidationError("invalid Binance order event")
    return NormalizedTestnetOrderEvent(
        exchange_name=ExchangeName.BINANCE,
        client_order_id=_optional_text(payload.get("c")),
        exchange_order_id=_optional_text(payload.get("i")),
        status=_status(
            payload.get("X"),
            {
                "NEW": OrderExecutionStatus.ACCEPTED,
                "PENDING_NEW": OrderExecutionStatus.SUBMITTED,
                "PARTIALLY_FILLED": OrderExecutionStatus.PARTIALLY_FILLED,
                "FILLED": OrderExecutionStatus.FILLED,
                "CANCELED": OrderExecutionStatus.CANCELLED,
                "REJECTED": OrderExecutionStatus.REJECTED,
                "EXPIRED": OrderExecutionStatus.TIMEOUT,
                "EXPIRED_IN_MATCH": OrderExecutionStatus.TIMEOUT,
            },
        ),
        event_id=_optional_text(payload.get("E")),
        filled_quantity=_optional_decimal(payload.get("z")),
    )


def _normalize_bybit(payload: dict[str, Any]) -> NormalizedTestnetOrderEvent:
    row = _first_mapping(payload.get("data"))
    return NormalizedTestnetOrderEvent(
        exchange_name=ExchangeName.BYBIT,
        client_order_id=_optional_text(row.get("orderLinkId")),
        exchange_order_id=_optional_text(row.get("orderId")),
        status=_status(
            row.get("orderStatus"),
            {
                "New": OrderExecutionStatus.ACCEPTED,
                "PartiallyFilled": OrderExecutionStatus.PARTIALLY_FILLED,
                "Filled": OrderExecutionStatus.FILLED,
                "Cancelled": OrderExecutionStatus.CANCELLED,
                "Rejected": OrderExecutionStatus.REJECTED,
                "Deactivated": OrderExecutionStatus.CANCELLED,
            },
        ),
        event_id=_optional_text(payload.get("id") or payload.get("creationTime")),
        filled_quantity=_optional_decimal(row.get("cumExecQty")),
    )


def _normalize_okx(payload: dict[str, Any]) -> NormalizedTestnetOrderEvent:
    row = _first_mapping(payload.get("data"))
    return NormalizedTestnetOrderEvent(
        exchange_name=ExchangeName.OKX,
        client_order_id=_optional_text(row.get("clOrdId")),
        exchange_order_id=_optional_text(row.get("ordId")),
        status=_status(
            row.get("state"),
            {
                "live": OrderExecutionStatus.ACCEPTED,
                "partially_filled": OrderExecutionStatus.PARTIALLY_FILLED,
                "filled": OrderExecutionStatus.FILLED,
                "canceled": OrderExecutionStatus.CANCELLED,
                "mmp_canceled": OrderExecutionStatus.CANCELLED,
            },
        ),
        event_id=_optional_text(row.get("uTime") or row.get("cTime")),
        filled_quantity=_optional_decimal(row.get("accFillSz")),
    )


def _status(
    raw_status: Any,
    mapping: dict[str, OrderExecutionStatus],
) -> OrderExecutionStatus:
    status = mapping.get(str(raw_status))
    if status is None:
        raise TestnetOrderEventValidationError("unsupported testnet order status")
    return status


def _first_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        raise TestnetOrderEventValidationError("testnet order event data is missing")
    return value[0]


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TestnetOrderEventValidationError("invalid filled quantity") from exc


def _safe_transition_details(
    event: NormalizedTestnetOrderEvent,
) -> dict[str, object]:
    details: dict[str, object] = {"exchange": event.exchange_name.value}
    if event.event_id:
        details["event_id"] = event.event_id
    if event.filled_quantity is not None:
        details["filled_quantity"] = str(event.filled_quantity)
    return details


def _ignored_result(reason: str) -> TestnetOrderLifecycleResult:
    return TestnetOrderLifecycleResult(
        matched=False,
        transitioned=False,
        duplicate=False,
        ignored=True,
        execution_id=None,
        status=None,
        reason=reason,
    )


def _execution_result(
    execution: OrderExecution,
    *,
    transitioned: bool = False,
    duplicate: bool = False,
    ignored: bool = False,
    reason: str,
) -> TestnetOrderLifecycleResult:
    return TestnetOrderLifecycleResult(
        matched=True,
        transitioned=transitioned,
        duplicate=duplicate,
        ignored=ignored,
        execution_id=execution.execution_id,
        status=OrderExecutionStatus(execution.status),
        reason=reason,
    )
