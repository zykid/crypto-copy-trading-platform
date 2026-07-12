from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderExecution, OrderExecutionStatus
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeHttpRequestError,
    ExchangeSecurityType,
    SignedExchangeHttpClient,
)
from app.services.exchange_accounts import get_exchange_credentials, get_owned_account
from app.services.testnet_http_client import create_testnet_signed_http_client
from app.services.testnet_order_lifecycle import (
    TestnetOrderLifecycleProcessor,
    TestnetOrderLifecycleResult,
    normalize_testnet_rest_order_status,
)

_PENDING_STATUSES = (
    OrderExecutionStatus.SUBMITTED,
    OrderExecutionStatus.ACCEPTED,
    OrderExecutionStatus.PARTIALLY_FILLED,
)


class TestnetOrderReconciliationBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class TestnetOrderReconciliationItem:
    execution_id: str
    status: str
    lifecycle_result: TestnetOrderLifecycleResult | None
    failure_type: str | None = None


@dataclass(frozen=True)
class TestnetOrderReconciliationResult:
    exchange_account_id: str
    attempted: int
    transitioned: int
    failed: int
    items: tuple[TestnetOrderReconciliationItem, ...]


def reconcile_pending_testnet_orders(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    http_client: SignedExchangeHttpClient | None = None,
) -> TestnetOrderReconciliationResult:
    """Explicitly refresh pending TESTNET orders through private REST lookups.

    The caller must invoke this service. It never opens a websocket, changes
    trading flags, or creates/submits an order.
    """
    account = get_owned_account(db, user_id=user_id, account_id=exchange_account_id)
    if account is None or not account.is_active:
        raise TestnetOrderReconciliationBlockedError("testnet exchange account was not found")
    if account.account_mode != AccountMode.TESTNET:
        raise TestnetOrderReconciliationBlockedError("account mode must be TESTNET")
    if account.exchange_name == ExchangeName.MOCK:
        raise TestnetOrderReconciliationBlockedError("mock exchange has no private REST lookup")
    if account.trading_enabled:
        raise TestnetOrderReconciliationBlockedError("trading must remain disabled")

    credentials = get_exchange_credentials(
        db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
    )
    if credentials is None:
        raise TestnetOrderReconciliationBlockedError("testnet API credentials are not configured")

    client = http_client or create_testnet_signed_http_client(
        exchange_name=account.exchange_name,
    )
    processor = TestnetOrderLifecycleProcessor(
        db=db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
    )
    executions = tuple(
        db.scalars(
            select(OrderExecution).where(
                OrderExecution.user_id == user_id,
                OrderExecution.exchange_account_id == exchange_account_id,
                OrderExecution.status.in_(_PENDING_STATUSES),
            )
        )
    )
    items = tuple(
        _reconcile_execution(
            execution=execution,
            exchange_name=account.exchange_name,
            credentials=credentials,
            client=client,
            processor=processor,
        )
        for execution in executions
    )
    result = TestnetOrderReconciliationResult(
        exchange_account_id=exchange_account_id,
        attempted=len(items),
        transitioned=sum(
            item.lifecycle_result.transitioned
            for item in items
            if item.lifecycle_result
        ),
        failed=sum(item.failure_type is not None for item in items),
        items=items,
    )
    _write_audit(db, user_id=user_id, result=result, exchange_name=account.exchange_name)
    return result


def _reconcile_execution(
    *,
    execution: OrderExecution,
    exchange_name: ExchangeName,
    credentials: ExchangeCredentials,
    client: SignedExchangeHttpClient,
    processor: TestnetOrderLifecycleProcessor,
) -> TestnetOrderReconciliationItem:
    try:
        response = client.get_private(
            _order_lookup_path(exchange_name),
            credentials=credentials,
            params=_order_lookup_params(execution, exchange_name),
            security_type=_security_type(exchange_name),
        )
        event = normalize_testnet_rest_order_status(
            exchange_name=exchange_name,
            payload=response,
        )
        lifecycle_result = processor.apply(
            event,
            transition_reason="testnet_rest_order_reconciliation",
        )
    except (ExchangeHttpRequestError, ValueError) as exc:
        failure_type = getattr(exc, "failure_type", "response_invalid")
        return TestnetOrderReconciliationItem(
            execution_id=execution.execution_id,
            status=execution.status,
            lifecycle_result=None,
            failure_type=failure_type,
        )
    return TestnetOrderReconciliationItem(
        execution_id=execution.execution_id,
        status=lifecycle_result.status.value if lifecycle_result.status else execution.status,
        lifecycle_result=lifecycle_result,
    )


def _order_lookup_path(exchange_name: ExchangeName) -> str:
    return {
        ExchangeName.BINANCE: "/api/v3/order",
        ExchangeName.BYBIT: "/v5/order/realtime",
        ExchangeName.OKX: "/api/v5/trade/order",
    }[exchange_name]


def _order_lookup_params(
    execution: OrderExecution,
    exchange_name: ExchangeName,
) -> dict[str, str]:
    if exchange_name == ExchangeName.BINANCE:
        return {"symbol": execution.symbol, "origClientOrderId": execution.client_order_id}
    if exchange_name == ExchangeName.BYBIT:
        return {"category": "spot", "orderLinkId": execution.client_order_id}
    return {
        "instId": _okx_symbol(execution.symbol),
        "clOrdId": execution.client_order_id,
    }


def _security_type(exchange_name: ExchangeName) -> ExchangeSecurityType:
    return (
        ExchangeSecurityType.OKX_DEMO_SIGNED
        if exchange_name == ExchangeName.OKX
        else ExchangeSecurityType.SIGNED
    )


def _okx_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if "-" in normalized:
        return normalized
    if normalized.endswith("USDT"):
        return f"{normalized[:-4]}-USDT"
    return normalized


def _write_audit(
    db: Session,
    *,
    user_id: str,
    exchange_name: ExchangeName,
    result: TestnetOrderReconciliationResult,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=result.exchange_account_id,
            action="testnet.order.reconciliation.requested",
            severity="WARNING" if result.failed else "INFO",
            payload={
                "exchange_name": exchange_name.value,
                "account_mode": AccountMode.TESTNET.value,
                "attempted": result.attempted,
                "transitioned": result.transitioned,
                "failed": result.failed,
            },
        )
    )
    db.commit()
