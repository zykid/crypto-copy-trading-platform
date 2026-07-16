from dataclasses import dataclass

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


class RealBalancesBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("real balances read is blocked")
        self.reasons = reasons


class RealBalancesAuthenticationError(RuntimeError):
    def __init__(self, *, failure_type: str, exchange_code: str | None = None) -> None:
        super().__init__("exchange balances request failed")
        self.failure_type = failure_type
        self.exchange_code = exchange_code


@dataclass(frozen=True)
class RealBalance:
    asset: str
    free: str | None
    locked: str | None
    total: str | None


@dataclass(frozen=True)
class RealBalancesResult:
    exchange_account_id: str
    exchange_name: ExchangeName
    balances: tuple[RealBalance, ...]


def read_real_balances(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    http_client: ExchangeHttpClient | None = None,
) -> RealBalancesResult:
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
            reasons.append("only OKX production balances are enabled")
        if account.trading_enabled:
            reasons.append("trading must remain disabled for balance display")

    credentials = (
        get_exchange_credentials(db, user_id=user_id, exchange_account_id=account.id)
        if account is not None
        else None
    )
    if account is not None and credentials is None:
        reasons.append("production API credentials must be configured")
    if reasons:
        raise RealBalancesBlockedError(tuple(reasons))

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
        balances = tuple(_sanitize_balance(item) for item in adapter.get_balances())
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
        raise RealBalancesAuthenticationError(
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
        raise RealBalancesAuthenticationError(failure_type="unexpected_error") from exc

    _write_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        loaded=True,
        asset_count=len(balances),
    )
    return RealBalancesResult(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        balances=balances,
    )


def _sanitize_balance(item: dict[str, object]) -> RealBalance:
    asset = item.get("asset")
    if not isinstance(asset, str) or not asset.strip():
        raise ValueError("exchange balance asset is missing")
    return RealBalance(
        asset=asset.strip().upper(),
        free=_optional_text(item.get("free")),
        locked=_optional_text(item.get("locked")),
        total=_optional_text(item.get("total")),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _write_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    exchange_name: ExchangeName,
    loaded: bool,
    asset_count: int | None = None,
    failure_type: str | None = None,
    exchange_code: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "exchange_name": exchange_name.value,
        "account_mode": AccountMode.REAL.value,
        "read_only": True,
        "loaded": loaded,
    }
    if asset_count is not None:
        payload["asset_count"] = asset_count
    if failure_type is not None:
        payload["failure_type"] = failure_type
    if exchange_code is not None:
        payload["exchange_code"] = exchange_code
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            action="real.read_only.balances.loaded",
            severity="INFO" if loaded else "WARNING",
            payload=payload,
        )
    )
    db.commit()
