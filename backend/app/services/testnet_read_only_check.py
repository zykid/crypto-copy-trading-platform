from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.exchanges.factory import create_exchange_adapter
from app.exchanges.http_client import ExchangeHttpClient
from app.services.exchange_accounts import get_exchange_credentials, get_owned_account
from app.services.testnet_http_client import create_testnet_signed_http_client


class TestnetReadOnlyCheckBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("testnet read-only check is blocked")
        self.reasons = reasons


class TestnetReadOnlyAccountNotFoundError(ValueError):
    pass


class TestnetReadOnlyAuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TestnetReadOnlyCheckResult:
    exchange_account_id: str
    exchange_name: ExchangeName
    authenticated: bool
    balance_asset_count: int


def run_testnet_read_only_check(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    testnet_adapters_enabled: bool,
    http_client: ExchangeHttpClient | None = None,
) -> TestnetReadOnlyCheckResult:
    account = get_owned_account(
        db,
        user_id=user_id,
        account_id=exchange_account_id,
    )
    if account is None:
        raise TestnetReadOnlyAccountNotFoundError("account not found")

    reasons: list[str] = []
    if not account.is_active:
        reasons.append("exchange account must be active")
    if account.account_mode != AccountMode.TESTNET:
        reasons.append("account mode must be TESTNET")
    if account.exchange_name == ExchangeName.MOCK:
        reasons.append("mock exchange does not support testnet authentication")
    if account.trading_enabled:
        reasons.append("trading must remain disabled during read-only checks")
    if not testnet_adapters_enabled:
        reasons.append("testnet adapters must be explicitly enabled")

    credentials = get_exchange_credentials(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    if credentials is None:
        reasons.append("testnet API credentials must be configured")

    if reasons:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            authenticated=False,
            reasons=tuple(reasons),
        )
        raise TestnetReadOnlyCheckBlockedError(tuple(reasons))

    client = http_client or create_testnet_signed_http_client(
        exchange_name=account.exchange_name,
    )
    adapter = create_exchange_adapter(
        account.exchange_name,
        testnet_adapters_enabled=True,
        http_client=client,
        credentials=credentials,
    )
    try:
        balances = adapter.get_balances()
    except Exception as exc:
        _write_audit(
            db,
            user_id=user_id,
            exchange_account_id=account.id,
            exchange_name=account.exchange_name,
            authenticated=False,
            reasons=("exchange authentication failed",),
        )
        raise TestnetReadOnlyAuthenticationError(
            "exchange authentication failed"
        ) from exc

    _write_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        authenticated=True,
        balance_asset_count=len(balances),
    )
    return TestnetReadOnlyCheckResult(
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
) -> None:
    payload: dict[str, object] = {
        "exchange_name": exchange_name.value,
        "authenticated": authenticated,
    }
    if reasons:
        payload["reasons"] = list(reasons)
    if balance_asset_count is not None:
        payload["balance_asset_count"] = balance_asset_count
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            action="testnet.read_only.authentication.checked",
            severity="INFO" if authenticated else "WARNING",
            payload=payload,
        )
    )
    db.commit()
