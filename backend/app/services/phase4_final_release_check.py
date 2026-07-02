from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import RiskSetting
from app.db.models.user import UserRole
from app.services.exchange_accounts import get_owned_account
from app.services.phase4_small_fund_review import PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP

PHASE4_FINAL_RELEASE_CHECK_ACK = "RECORD_PHASE4_FINAL_RELEASE_CHECK_ONLY"


class Phase4FinalReleaseCheckBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("phase 4 final release check is blocked")
        self.reasons = reasons


@dataclass(frozen=True)
class Phase4FinalReleaseCheck:
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    max_notional: Decimal
    review_audit_log_id: str
    order_window_audit_log_id: str
    order_submission_authorized: bool = False
    trading_flags_changed: bool = False


def record_phase4_final_release_check(
    db: Session,
    *,
    user_id: str,
    user_role: UserRole,
    exchange_account_id: str,
    max_notional: Decimal,
    dedicated_account_confirmed: bool,
    account_empty_confirmed: bool,
    withdrawals_disabled_confirmed: bool,
    delete_api_key_after_test_confirmed: bool,
    first_order_stop_review_confirmed: bool,
    no_live_order_submission_confirmed: bool,
    acknowledgement: str,
) -> Phase4FinalReleaseCheck:
    account = get_owned_account(db, user_id=user_id, account_id=exchange_account_id)
    if account is None:
        raise ValueError("account not found")

    risk_settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user_id,
            RiskSetting.exchange_account_id == account.id,
        )
    )
    review_audit = _latest_required_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        action="real.small_fund.review_recorded",
    )
    order_window_audit = _latest_required_audit(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        action="real.small_fund.order_window.approval_recorded",
    )
    review_max_notional = _audit_decimal(review_audit, "max_notional")
    order_window_max_notional = _audit_decimal(order_window_audit, "max_notional")

    reasons = _blocked_reasons(
        user_role=user_role,
        exchange_name=account.exchange_name,
        account_is_active=account.is_active,
        account_mode=account.account_mode,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_settings=risk_settings,
        review_audit_configured=review_audit is not None,
        order_window_audit_configured=order_window_audit is not None,
        review_max_notional=review_max_notional,
        order_window_max_notional=order_window_max_notional,
        max_notional=max_notional,
        dedicated_account_confirmed=dedicated_account_confirmed,
        account_empty_confirmed=account_empty_confirmed,
        withdrawals_disabled_confirmed=withdrawals_disabled_confirmed,
        delete_api_key_after_test_confirmed=delete_api_key_after_test_confirmed,
        first_order_stop_review_confirmed=first_order_stop_review_confirmed,
        no_live_order_submission_confirmed=no_live_order_submission_confirmed,
        acknowledgement=acknowledgement,
    )
    if reasons:
        raise Phase4FinalReleaseCheckBlockedError(reasons)

    audit_log = AuditLog(
        user_id=user_id,
        exchange_account_id=account.id,
        action="real.small_fund.final_release_check_recorded",
        severity="CRITICAL",
        payload={
            "exchange_name": account.exchange_name.value,
            "account_mode": account.account_mode.value,
            "max_notional": str(max_notional),
            "max_notional_cap": str(PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP),
            "review_audit_log_id": review_audit.id if review_audit else "",
            "order_window_audit_log_id": order_window_audit.id if order_window_audit else "",
            "dedicated_account_confirmed": dedicated_account_confirmed,
            "account_empty_confirmed": account_empty_confirmed,
            "withdrawals_disabled_confirmed": withdrawals_disabled_confirmed,
            "delete_api_key_after_test_confirmed": delete_api_key_after_test_confirmed,
            "first_order_stop_review_confirmed": first_order_stop_review_confirmed,
            "no_live_order_submission_confirmed": no_live_order_submission_confirmed,
            "acknowledgement": acknowledgement,
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return Phase4FinalReleaseCheck(
        audit_log_id=audit_log.id,
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        max_notional=max_notional,
        review_audit_log_id=review_audit.id if review_audit else "",
        order_window_audit_log_id=order_window_audit.id if order_window_audit else "",
    )


def _latest_required_audit(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    action: str,
) -> AuditLog | None:
    return db.scalar(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.exchange_account_id == exchange_account_id,
            AuditLog.action == action,
            AuditLog.severity == "CRITICAL",
        )
        .order_by(AuditLog.created_at.desc())
    )


def _audit_decimal(audit_log: AuditLog | None, key: str) -> Decimal | None:
    if audit_log is None:
        return None
    try:
        return Decimal(str(audit_log.payload.get(key, "")))
    except Exception:
        return None


def _blocked_reasons(
    *,
    user_role: UserRole,
    exchange_name: ExchangeName,
    account_is_active: bool,
    account_mode: AccountMode,
    exchange_account_trading_enabled: bool,
    risk_settings: RiskSetting | None,
    review_audit_configured: bool,
    order_window_audit_configured: bool,
    review_max_notional: Decimal | None,
    order_window_max_notional: Decimal | None,
    max_notional: Decimal,
    dedicated_account_confirmed: bool,
    account_empty_confirmed: bool,
    withdrawals_disabled_confirmed: bool,
    delete_api_key_after_test_confirmed: bool,
    first_order_stop_review_confirmed: bool,
    no_live_order_submission_confirmed: bool,
    acknowledgement: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if user_role != UserRole.SUPER_ADMIN:
        reasons.append("super administrator privileges are required for Phase 4 final check")
    if exchange_name != ExchangeName.OKX:
        reasons.append("Phase 4 final check currently supports OKX REAL accounts only")
    if not account_is_active:
        reasons.append("exchange account must be active before Phase 4 final check")
    if account_mode != AccountMode.REAL:
        reasons.append("account mode must be REAL before Phase 4 final check")
    if exchange_account_trading_enabled:
        reasons.append("exchange account trading_enabled must remain false")
    if risk_settings is None:
        reasons.append("risk settings must exist before Phase 4 final check")
    elif risk_settings.trading_enabled:
        reasons.append("risk settings trading_enabled must remain false")
    if not review_audit_configured:
        reasons.append("Phase 4 small-fund review audit is required")
    if not order_window_audit_configured:
        reasons.append("Phase 4 order-window audit is required")
    if review_max_notional is None:
        reasons.append("Phase 4 small-fund review max_notional is invalid")
    if order_window_max_notional is None:
        reasons.append("Phase 4 order-window max_notional is invalid")
    if max_notional <= 0:
        reasons.append("final check max_notional must be greater than zero")
    if max_notional > PHASE4_SMALL_FUND_MAX_NOTIONAL_CAP:
        reasons.append("final check max_notional exceeds the Phase 4 cap")
    if review_max_notional is not None and max_notional > review_max_notional:
        reasons.append("final check max_notional exceeds the reviewed small-fund cap")
    if order_window_max_notional is not None and max_notional > order_window_max_notional:
        reasons.append("final check max_notional exceeds the order-window cap")
    if not dedicated_account_confirmed:
        reasons.append("dedicated test account confirmation is required")
    if not account_empty_confirmed:
        reasons.append("empty-account confirmation is required")
    if not withdrawals_disabled_confirmed:
        reasons.append("withdrawal-disabled confirmation is required")
    if not delete_api_key_after_test_confirmed:
        reasons.append("API-key deletion-after-test confirmation is required")
    if not first_order_stop_review_confirmed:
        reasons.append("first-order stop-and-review confirmation is required")
    if not no_live_order_submission_confirmed:
        reasons.append("no-live-order-submission confirmation is required")
    if acknowledgement != PHASE4_FINAL_RELEASE_CHECK_ACK:
        reasons.append("explicit Phase 4 final release-check acknowledgement is required")
    return tuple(reasons)
