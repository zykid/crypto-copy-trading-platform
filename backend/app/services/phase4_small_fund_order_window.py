from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderSide, RiskSetting
from app.db.models.user import UserRole
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account
from app.services.phase4_small_fund_review import PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP

PHASE4_SMALL_FUND_ORDER_WINDOW_ACK = "APPROVE_REAL_SMALL_FUND_ORDER_WINDOW_ONLY"


class Phase4SmallFundOrderWindowBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("phase 4 small-fund order window approval is blocked")
        self.reasons = reasons


@dataclass(frozen=True)
class Phase4SmallFundOrderWindowApproval:
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    symbol: str
    side: OrderSide
    max_quantity: Decimal
    limit_price: Decimal
    max_notional: Decimal
    duration_minutes: int
    review_audit_log_id: str
    read_only_audit_log_id: str
    order_submission_authorized: bool = False
    trading_flags_changed: bool = False


def record_phase4_small_fund_order_window_approval(
    db: Session,
    *,
    user_id: str,
    user_role: UserRole,
    exchange_account_id: str,
    symbol: str,
    side: OrderSide,
    max_quantity: Decimal,
    limit_price: Decimal,
    max_notional: Decimal,
    duration_minutes: int,
    acknowledgement: str,
) -> Phase4SmallFundOrderWindowApproval:
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
    read_only_audit = _latest_successful_real_read_only_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    review_audit = _latest_phase4_review_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    review_max_notional = _review_max_notional(review_audit)

    reasons = _approval_blocked_reasons(
        user_role=user_role,
        exchange_name=account.exchange_name,
        account_is_active=account.is_active,
        account_mode=account.account_mode,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_settings=risk_settings,
        api_key_configured=secret_metadata is not None,
        passphrase_configured=secret_metadata is not None
        and secret_metadata.encrypted_passphrase is not None,
        read_only_audit_configured=read_only_audit is not None,
        review_audit_configured=review_audit is not None,
        review_max_notional=review_max_notional,
        symbol=symbol,
        max_quantity=max_quantity,
        limit_price=limit_price,
        max_notional=max_notional,
        duration_minutes=duration_minutes,
        acknowledgement=acknowledgement,
    )
    if reasons:
        raise Phase4SmallFundOrderWindowBlockedError(reasons)

    normalized_symbol = symbol.strip().upper()
    audit_log = AuditLog(
        user_id=user_id,
        exchange_account_id=account.id,
        action="real.small_fund.order_window.approval_recorded",
        severity="CRITICAL",
        payload={
            "exchange_name": account.exchange_name.value,
            "account_mode": account.account_mode.value,
            "symbol": normalized_symbol,
            "side": side.value,
            "max_quantity": str(max_quantity),
            "limit_price": str(limit_price),
            "max_notional": str(max_notional),
            "duration_minutes": duration_minutes,
            "acknowledgement": acknowledgement,
            "review_audit_log_id": review_audit.id if review_audit else "",
            "read_only_audit_log_id": read_only_audit.id if read_only_audit else "",
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return Phase4SmallFundOrderWindowApproval(
        audit_log_id=audit_log.id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        symbol=normalized_symbol,
        side=side,
        max_quantity=max_quantity,
        limit_price=limit_price,
        max_notional=max_notional,
        duration_minutes=duration_minutes,
        review_audit_log_id=review_audit.id if review_audit else "",
        read_only_audit_log_id=read_only_audit.id if read_only_audit else "",
    )


def _latest_successful_real_read_only_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
) -> AuditLog | None:
    return db.scalar(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.exchange_account_id == exchange_account_id,
            AuditLog.action == "real.read_only.authentication.checked",
            AuditLog.severity == "INFO",
        )
        .order_by(AuditLog.created_at.desc())
    )


def _latest_phase4_review_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
) -> AuditLog | None:
    return db.scalar(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.exchange_account_id == exchange_account_id,
            AuditLog.action == "real.small_fund.review_recorded",
            AuditLog.severity == "CRITICAL",
        )
        .order_by(AuditLog.created_at.desc())
    )


def _review_max_notional(review_audit: AuditLog | None) -> Decimal | None:
    if review_audit is None:
        return None
    try:
        return Decimal(str(review_audit.payload.get("max_notional", "")))
    except Exception:
        return None


def _approval_blocked_reasons(
    *,
    user_role: UserRole,
    exchange_name: ExchangeName,
    account_is_active: bool,
    account_mode: AccountMode,
    exchange_account_trading_enabled: bool,
    risk_settings: RiskSetting | None,
    api_key_configured: bool,
    passphrase_configured: bool,
    read_only_audit_configured: bool,
    review_audit_configured: bool,
    review_max_notional: Decimal | None,
    symbol: str,
    max_quantity: Decimal,
    limit_price: Decimal,
    max_notional: Decimal,
    duration_minutes: int,
    acknowledgement: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if user_role != UserRole.SUPER_ADMIN:
        reasons.append("super administrator privileges are required for Phase 4 order window")
    if exchange_name != ExchangeName.OKX:
        reasons.append("Phase 4 order window currently supports OKX REAL accounts only")
    if not account_is_active:
        reasons.append("exchange account must be active before Phase 4 order window")
    if account_mode != AccountMode.REAL:
        reasons.append("account mode must be REAL before Phase 4 order window")
    if exchange_account_trading_enabled:
        reasons.append("exchange account trading_enabled must remain false")
    if risk_settings is None:
        reasons.append("risk settings must exist before Phase 4 order window")
    elif risk_settings.trading_enabled:
        reasons.append("risk settings trading_enabled must remain false")
    if not api_key_configured:
        reasons.append("encrypted API key metadata must exist before Phase 4 order window")
    if not passphrase_configured:
        reasons.append("OKX REAL API passphrase metadata must exist before Phase 4 order window")
    if not read_only_audit_configured:
        reasons.append("successful REAL read-only authentication audit is required")
    if not review_audit_configured:
        reasons.append("Phase 4 small-fund review audit is required")
    if review_max_notional is None:
        reasons.append("Phase 4 small-fund review max_notional is invalid")
    if not symbol.strip():
        reasons.append("order window symbol is required")
    if max_quantity <= 0:
        reasons.append("order window max_quantity must be greater than zero")
    if limit_price <= 0:
        reasons.append("order window limit_price must be greater than zero")
    if max_notional <= 0:
        reasons.append("order window max_notional must be greater than zero")
    if max_notional > PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP:
        reasons.append("order window max_notional exceeds the Phase 4 cap")
    if review_max_notional is not None and max_notional > review_max_notional:
        reasons.append("order window max_notional exceeds the reviewed small-fund cap")
    if max_quantity > 0 and limit_price > 0 and max_quantity * limit_price > max_notional:
        reasons.append("order window quantity multiplied by limit_price exceeds max_notional")
    if duration_minutes < 1 or duration_minutes > 10:
        reasons.append("Phase 4 order window duration must be between 1 and 10 minutes")
    if acknowledgement != PHASE4_SMALL_FUND_ORDER_WINDOW_ACK:
        reasons.append("explicit Phase 4 small-fund order window acknowledgement is required")
    return tuple(reasons)
