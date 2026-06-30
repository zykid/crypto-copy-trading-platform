from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderSide, RiskSetting
from app.db.models.user import UserRole
from app.exchanges.testnet_config import TESTNET_ENDPOINTS
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account

TESTNET_ORDER_WINDOW_APPROVAL_ACK = "APPROVE_TESTNET_ORDER_WINDOW_ONLY"


class TestnetOrderWindowApprovalBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("testnet order window approval is blocked")
        self.reasons = reasons


class TestnetOrderWindowAuthorizationError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("testnet order window authorization is invalid")
        self.reasons = reasons


@dataclass(frozen=True)
class TestnetOrderWindowApproval:
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    symbol: str
    side: OrderSide
    max_quantity: Decimal
    max_notional: Decimal
    duration_minutes: int
    order_submission_authorized: bool = False
    trading_flags_changed: bool = False


@dataclass(frozen=True)
class TestnetOrderWindowAuthorization:
    audit_log_id: str
    expires_at: datetime


def record_testnet_order_window_approval(
    db: Session,
    *,
    user_id: str,
    user_role: UserRole,
    exchange_account_id: str,
    symbol: str,
    side: OrderSide,
    max_quantity: Decimal,
    max_notional: Decimal,
    duration_minutes: int,
    acknowledgement: str,
    testnet_adapters_enabled: bool,
) -> TestnetOrderWindowApproval:
    account = get_owned_account(
        db,
        user_id=user_id,
        account_id=exchange_account_id,
    )
    if account is None:
        raise ValueError("account not found")

    risk_settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user_id,
            RiskSetting.exchange_account_id == account.id,
        )
    )
    secret_metadata = get_api_key_secret_metadata(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )

    reasons = _approval_blocked_reasons(
        user_role=user_role,
        exchange_name=account.exchange_name,
        account_is_active=account.is_active,
        account_mode=account.account_mode,
        testnet_adapters_enabled=testnet_adapters_enabled,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_settings=risk_settings,
        api_key_configured=secret_metadata is not None,
        duration_minutes=duration_minutes,
        acknowledgement=acknowledgement,
    )
    if reasons:
        raise TestnetOrderWindowApprovalBlockedError(reasons)

    audit_log = AuditLog(
        user_id=user_id,
        exchange_account_id=account.id,
        action="testnet.order_window.approval_recorded",
        severity="WARNING",
        payload={
            "exchange_name": account.exchange_name.value,
            "account_mode": account.account_mode.value,
            "symbol": symbol,
            "side": side.value,
            "max_quantity": str(max_quantity),
            "max_notional": str(max_notional),
            "duration_minutes": duration_minutes,
            "acknowledgement": acknowledgement,
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return TestnetOrderWindowApproval(
        audit_log_id=audit_log.id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        symbol=symbol,
        side=side,
        max_quantity=max_quantity,
        max_notional=max_notional,
        duration_minutes=duration_minutes,
    )


def require_valid_testnet_order_window_authorization(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    symbol: str,
    side: OrderSide,
    quantity: Decimal,
    price: Decimal | None,
    now: datetime | None = None,
) -> TestnetOrderWindowAuthorization:
    reasons: list[str] = []
    normalized_symbol = symbol.strip().upper()
    if price is None:
        reasons.append("limit price is required for approved testnet order windows")

    audit_log = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.exchange_account_id == exchange_account_id,
            AuditLog.action == "testnet.order_window.approval_recorded",
        )
        .order_by(AuditLog.created_at.desc())
    )
    if audit_log is None:
        reasons.append("valid testnet order window approval audit log is required")
        raise TestnetOrderWindowAuthorizationError(tuple(reasons))

    payload = audit_log.payload
    approved_symbol = str(payload.get("symbol", "")).strip().upper()
    approved_side = str(payload.get("side", ""))
    max_quantity = _decimal_from_payload(payload.get("max_quantity"), "max_quantity", reasons)
    max_notional = _decimal_from_payload(payload.get("max_notional"), "max_notional", reasons)
    duration_minutes = _int_from_payload(
        payload.get("duration_minutes"),
        "duration_minutes",
        reasons,
    )

    if approved_symbol != normalized_symbol:
        reasons.append("testnet order symbol must match the approved window")
    if approved_side != side.value:
        reasons.append("testnet order side must match the approved window")
    if max_quantity is not None and quantity > max_quantity:
        reasons.append("testnet order quantity exceeds the approved window")
    if price is not None and max_notional is not None and quantity * price > max_notional:
        reasons.append("testnet order notional exceeds the approved window")

    created_at = _as_utc(audit_log.created_at)
    now_utc = _as_utc(now or datetime.now(UTC))
    expires_at = created_at + timedelta(minutes=duration_minutes or 0)
    if duration_minutes is None or duration_minutes < 1 or duration_minutes > 10:
        reasons.append("testnet order window audit duration is invalid")
    elif now_utc > expires_at:
        reasons.append("testnet order window approval has expired")

    if reasons:
        raise TestnetOrderWindowAuthorizationError(tuple(reasons))
    return TestnetOrderWindowAuthorization(
        audit_log_id=audit_log.id,
        expires_at=expires_at,
    )


def _approval_blocked_reasons(
    *,
    user_role: UserRole,
    exchange_name: ExchangeName,
    account_is_active: bool,
    account_mode: AccountMode,
    testnet_adapters_enabled: bool,
    exchange_account_trading_enabled: bool,
    risk_settings: RiskSetting | None,
    api_key_configured: bool,
    duration_minutes: int,
    acknowledgement: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if user_role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        reasons.append("admin privileges are required to approve a testnet order window")
    if exchange_name not in TESTNET_ENDPOINTS:
        reasons.append("exchange does not support testnet order routing")
    if not account_is_active:
        reasons.append("exchange account must be active before approving an order window")
    if account_mode != AccountMode.TESTNET:
        reasons.append("account mode must be TESTNET before approving an order window")
    if testnet_adapters_enabled:
        reasons.append("TESTNET_ADAPTERS_ENABLED must still be false before approval is recorded")
    if exchange_account_trading_enabled:
        reasons.append("exchange account trading_enabled must still be false before approval")
    if risk_settings is None:
        reasons.append("risk settings must exist before approving an order window")
    elif risk_settings.trading_enabled:
        reasons.append("risk settings trading_enabled must still be false before approval")
    if not api_key_configured:
        reasons.append("encrypted API key metadata must exist before approving an order window")
    if duration_minutes < 1 or duration_minutes > 10:
        reasons.append("testnet order window duration must be between 1 and 10 minutes")
    if acknowledgement != TESTNET_ORDER_WINDOW_APPROVAL_ACK:
        reasons.append("explicit testnet order window acknowledgement is required")
    return tuple(reasons)


def _decimal_from_payload(
    value: object,
    field_name: str,
    reasons: list[str],
) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        reasons.append(f"testnet order window audit {field_name} is invalid")
        return None


def _int_from_payload(
    value: object,
    field_name: str,
    reasons: list[str],
) -> int | None:
    try:
        return int(str(value))
    except Exception:
        reasons.append(f"testnet order window audit {field_name} is invalid")
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
