from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.exchanges.factory import create_exchange_adapter
from app.exchanges.http_client import (
    ExchangeHttpClient,
    ExchangeHttpRequestError,
    SignedExchangeHttpClient,
)
from app.services.exchange_accounts import get_exchange_credentials, get_owned_account


class RealOpenOrdersBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("real open orders read is blocked")
        self.reasons = reasons


class RealOpenOrdersAuthenticationError(RuntimeError):
    def __init__(self, *, failure_type: str, exchange_code: str | None = None) -> None:
        super().__init__("exchange open orders request failed")
        self.failure_type = failure_type
        self.exchange_code = exchange_code


@dataclass(frozen=True)
class RealOpenOrdersResult:
    exchange_account_id: str
    exchange_name: ExchangeName
    orders: tuple[dict[str, Any], ...]


def read_real_open_orders(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    http_client: ExchangeHttpClient | None = None,
) -> RealOpenOrdersResult:
    account = get_owned_account(db, user_id=user_id, account_id=exchange_account_id)
    reasons: list[str] = []
    if account is None:
        reasons.append("account not found")
    else:
        if not account.is_active:
            reasons.append("exchange account must be active")
        if account.account_mode != AccountMode.REAL:
            reasons.append("account mode must be REAL")
        if account.exchange_name != ExchangeName.OKX:
            reasons.append("only OKX production open orders are enabled")
        if account.trading_enabled:
            reasons.append("trading must remain disabled for order display")

    credentials = (
        get_exchange_credentials(db, user_id=user_id, exchange_account_id=account.id)
        if account is not None
        else None
    )
    if account is not None and credentials is None:
        reasons.append("production API credentials must be configured")
    if reasons:
        raise RealOpenOrdersBlockedError(tuple(reasons))

    client = http_client or SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://www.okx.com",
    )
    adapter = create_exchange_adapter(
        ExchangeName.OKX,
        testnet_adapters_enabled=True,
        http_client=client,
        credentials=credentials,
        okx_demo_trading=False,
    )
    try:
        orders = tuple(adapter.get_open_orders())
    except ExchangeHttpRequestError as exc:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            loaded=False,
            failure_type=exc.failure_type,
            exchange_code=exc.exchange_code,
        )
        raise RealOpenOrdersAuthenticationError(
            failure_type=exc.failure_type,
            exchange_code=exc.exchange_code,
        ) from exc
    except Exception as exc:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            loaded=False,
            failure_type="unexpected_error",
        )
        raise RealOpenOrdersAuthenticationError(failure_type="unexpected_error") from exc

    _write_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        loaded=True,
        order_count=len(orders),
    )
    return RealOpenOrdersResult(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        orders=orders,
    )


def _write_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    exchange_name: ExchangeName,
    loaded: bool,
    order_count: int | None = None,
    failure_type: str | None = None,
    exchange_code: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "exchange_name": exchange_name.value,
        "account_mode": AccountMode.REAL.value,
        "read_only": True,
        "loaded": loaded,
    }
    if order_count is not None:
        payload["order_count"] = order_count
    if failure_type is not None:
        payload["failure_type"] = failure_type
    if exchange_code is not None:
        payload["exchange_code"] = exchange_code
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            action="real.read_only.open_orders.loaded",
            severity="INFO" if loaded else "WARNING",
            payload=payload,
        )
    )
    db.commit()
