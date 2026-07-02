from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import RiskSetting
from app.db.models.user import UserRole
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account

PHASE4_SMALL_FUND_REVIEW_ACK = "ACKNOWLEDGE_SMALL_FUND_REVIEW_ONLY"
PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP = Decimal("100")


class Phase4SmallFundReviewBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("phase 4 small-fund review is blocked")
        self.reasons = reasons


@dataclass(frozen=True)
class Phase4SmallFundReview:
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    max_notional: Decimal
    read_only_audit_log_id: str
    order_submission_authorized: bool = False
    trading_flags_changed: bool = False


def record_phase4_small_fund_review(
    db: Session,
    *,
    user_id: str,
    user_role: UserRole,
    exchange_account_id: str,
    max_notional: Decimal,
    acknowledgement: str,
) -> Phase4SmallFundReview:
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

    reasons = _review_blocked_reasons(
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
        max_notional=max_notional,
        acknowledgement=acknowledgement,
    )
    if reasons:
        raise Phase4SmallFundReviewBlockedError(reasons)

    audit_log = AuditLog(
        user_id=user_id,
        exchange_account_id=account.id,
        action="real.small_fund.review_recorded",
        severity="CRITICAL",
        payload={
            "exchange_name": account.exchange_name.value,
            "account_mode": account.account_mode.value,
            "max_notional": str(max_notional),
            "max_notional_cap": str(PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP),
            "acknowledgement": acknowledgement,
            "read_only_audit_log_id": read_only_audit.id if read_only_audit else "",
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return Phase4SmallFundReview(
        audit_log_id=audit_log.id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        max_notional=max_notional,
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


def _review_blocked_reasons(
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
    max_notional: Decimal,
    acknowledgement: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if user_role != UserRole.SUPER_ADMIN:
        reasons.append("super administrator privileges are required for Phase 4 review")
    if exchange_name != ExchangeName.OKX:
        reasons.append("Phase 4 review currently supports OKX REAL accounts only")
    if not account_is_active:
        reasons.append("exchange account must be active before Phase 4 review")
    if account_mode != AccountMode.REAL:
        reasons.append("account mode must be REAL before Phase 4 review")
    if exchange_account_trading_enabled:
        reasons.append("exchange account trading_enabled must remain false")
    if risk_settings is None:
        reasons.append("risk settings must exist before Phase 4 review")
    elif risk_settings.trading_enabled:
        reasons.append("risk settings trading_enabled must remain false")
    if not api_key_configured:
        reasons.append("encrypted API key metadata must exist before Phase 4 review")
    if not passphrase_configured:
        reasons.append("OKX REAL API passphrase metadata must exist before Phase 4 review")
    if not read_only_audit_configured:
        reasons.append("successful REAL read-only authentication audit is required")
    if max_notional <= 0:
        reasons.append("small-fund max_notional must be greater than zero")
    if max_notional > PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP:
        reasons.append("small-fund max_notional exceeds the Phase 4 cap")
    if acknowledgement != PHASE4_SMALL_FUND_REVIEW_ACK:
        reasons.append("explicit Phase 4 small-fund review acknowledgement is required")
    return tuple(reasons)
