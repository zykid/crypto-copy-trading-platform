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


class RealReadOnlyCheckBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("real read-only check is blocked")
        self.reasons = reasons


class RealReadOnlyAccountNotFoundError(ValueError):
    pass


class RealReadOnlyAuthenticationError(RuntimeError):
    def __init__(
        self,
        *,
        failure_type: str,
        exchange_code: str | None = None,
    ) -> None:
        super().__init__("exchange authentication failed")
        self.failure_type = failure_type
        self.exchange_code = exchange_code


@dataclass(frozen=True)
class RealReadOnlyCheckResult:
    exchange_account_id: str
    exchange_name: ExchangeName
    authenticated: bool
    balance_asset_count: int


def run_real_read_only_check(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    http_client: ExchangeHttpClient | None = None,
) -> RealReadOnlyCheckResult:
    account = get_owned_account(db, user_id=user_id, account_id=exchange_account_id)
    if account is None:
        raise RealReadOnlyAccountNotFoundError("account not found")

    reasons: list[str] = []
    if not account.is_active:
        reasons.append("exchange account must be active")
    if account.account_mode != AccountMode.REAL:
        reasons.append("account mode must be REAL")
    if account.exchange_name != ExchangeName.OKX:
        reasons.append("only OKX production read-only authentication is enabled")
    if account.trading_enabled:
        reasons.append("trading must remain disabled during production read-only checks")

    credentials = get_exchange_credentials(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    if credentials is None:
        reasons.append("production API credentials must be configured")

    if reasons:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            authenticated=False,
            reasons=tuple(reasons),
        )
        raise RealReadOnlyCheckBlockedError(tuple(reasons))

    client = http_client or SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://www.okx.com",
    )
    adapter = create_exchange_adapter(
        account.exchange_name,
        testnet_adapters_enabled=True,
        http_client=client,
        credentials=credentials,
        okx_demo_trading=False,
    )
    try:
        balances = adapter.get_balances()
    except ExchangeHttpRequestError as exc:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            authenticated=False,
            reasons=("exchange authentication failed",),
            failure_type=exc.failure_type,
            exchange_code=exc.exchange_code,
        )
        raise RealReadOnlyAuthenticationError(
            failure_type=exc.failure_type,
            exchange_code=exc.exchange_code,
        ) from exc
    except Exception as exc:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            authenticated=False,
            reasons=("exchange authentication failed",),
            failure_type="unexpected_error",
        )
        raise RealReadOnlyAuthenticationError(failure_type="unexpected_error") from exc

    _write_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        authenticated=True,
        balance_asset_count=len(balances),
    )
    return RealReadOnlyCheckResult(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        authenticated=True,
        balance_asset_count=len(balances),
    )


def _write_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    exchange_name: ExchangeName,
    authenticated: bool,
    reasons: tuple[str, ...] = (),
    balance_asset_count: int | None = None,
    failure_type: str | None = None,
    exchange_code: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "exchange_name": exchange_name.value,
        "authenticated": authenticated,
        "account_mode": AccountMode.REAL.value,
    }
    if reasons:
        payload["reasons"] = list(reasons)
    if balance_asset_count is not None:
        payload["balance_asset_count"] = balance_asset_count
    if failure_type is not None:
        payload["failure_type"] = failure_type
    if exchange_code is not None:
        payload["exchange_code"] = exchange_code
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            action="real.read_only.authentication.checked",
            severity="INFO" if authenticated else "WARNING",
            payload=payload,
        )
    )
    db.commit()
