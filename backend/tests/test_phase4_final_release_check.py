from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.exchange_accounts import record_final_release_check
from app.db.models.exchange_account import AccountMode, ExchangeAccount, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import RiskSetting
from app.db.models.user import User, UserRole
from app.schemas.exchange_account import Phase4FinalReleaseCheckRequest
from app.services.phase4_final_release_check import (
    PHASE4_FINAL_RELEASE_CHECK_ACK,
    Phase4FinalReleaseCheckBlockedError,
    record_phase4_final_release_check,
)
from app.services.phase4_small_fund_order_window import (
    PHASE4_SMALL_FUND_ORDER_WINDOW_ACK,
)
from app.services.phase4_small_fund_review import PHASE4_SMALL_FUND_REVIEW_ACK


def _user(role: UserRole = UserRole.SUPER_ADMIN) -> User:
    return User(
        email="phase4-final@example.com",
        username="phase4_final_operator",
        password_hash="hashed",
        role=role,
    )


def _real_okx_account(owner: User, *, trading_enabled: bool = False) -> ExchangeAccount:
    return ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.REAL,
        account_label="OKX production read only",
        trading_enabled=trading_enabled,
    )


def _add_risk_settings(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
    trading_enabled: bool = False,
) -> None:
    db_session.add(
        RiskSetting(
            user_id=owner.id,
            exchange_account_id=account.id,
            trading_enabled=trading_enabled,
            blocked_symbols=[],
        )
    )
    db_session.commit()


def _add_phase4_review_audit(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
    max_notional: str = "25",
) -> AuditLog:
    audit = AuditLog(
        user_id=owner.id,
        exchange_account_id=account.id,
        action="real.small_fund.review_recorded",
        severity="CRITICAL",
        payload={
            "exchange_name": "okx",
            "account_mode": "REAL",
            "max_notional": max_notional,
            "max_notional_cap": "100",
            "acknowledgement": PHASE4_SMALL_FUND_REVIEW_ACK,
            "read_only_audit_log_id": "read-only-audit-id",
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def _add_phase4_order_window_audit(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
    max_notional: str = "20",
) -> AuditLog:
    audit = AuditLog(
        user_id=owner.id,
        exchange_account_id=account.id,
        action="real.small_fund.order_window.approval_recorded",
        severity="CRITICAL",
        payload={
            "exchange_name": "okx",
            "account_mode": "REAL",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "max_quantity": "0.001",
            "limit_price": "20000",
            "max_notional": max_notional,
            "duration_minutes": 5,
            "acknowledgement": PHASE4_SMALL_FUND_ORDER_WINDOW_ACK,
            "review_audit_log_id": "review-audit-id",
            "read_only_audit_log_id": "read-only-audit-id",
            "order_submission_authorized": False,
            "trading_flags_changed": False,
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def _ready_account(db_session: Session) -> tuple[User, ExchangeAccount, AuditLog, AuditLog]:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    review_audit = _add_phase4_review_audit(db_session, owner=owner, account=account)
    window_audit = _add_phase4_order_window_audit(db_session, owner=owner, account=account)
    return owner, account, review_audit, window_audit


def _record_final_check(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
    max_notional: Decimal = Decimal("20"),
):
    return record_phase4_final_release_check(
        db_session,
        user_id=owner.id,
        user_role=owner.role,
        exchange_account_id=account.id,
        max_notional=max_notional,
        dedicated_account_confirmed=True,
        account_empty_confirmed=True,
        withdrawals_disabled_confirmed=True,
        delete_api_key_after_test_confirmed=True,
        first_order_stop_review_confirmed=True,
        no_live_order_submission_confirmed=True,
        acknowledgement=PHASE4_FINAL_RELEASE_CHECK_ACK,
    )


def test_phase4_final_release_check_records_audit_without_authorizing_orders(
    db_session: Session,
) -> None:
    owner, account, review_audit, window_audit = _ready_account(db_session)

    final_check = _record_final_check(db_session, owner=owner, account=account)

    assert final_check.exchange_account_id == account.id
    assert final_check.review_audit_log_id == review_audit.id
    assert final_check.order_window_audit_log_id == window_audit.id
    assert final_check.order_submission_authorized is False
    assert final_check.trading_flags_changed is False

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "real.small_fund.final_release_check_recorded"
        )
    )
    assert audit is not None
    assert audit.id == final_check.audit_log_id
    assert audit.severity == "CRITICAL"
    assert audit.payload == {
        "exchange_name": "okx",
        "account_mode": "REAL",
        "max_notional": "20",
        "max_notional_cap": "100",
        "review_audit_log_id": review_audit.id,
        "order_window_audit_log_id": window_audit.id,
        "dedicated_account_confirmed": True,
        "account_empty_confirmed": True,
        "withdrawals_disabled_confirmed": True,
        "delete_api_key_after_test_confirmed": True,
        "first_order_stop_review_confirmed": True,
        "no_live_order_submission_confirmed": True,
        "acknowledgement": PHASE4_FINAL_RELEASE_CHECK_ACK,
        "order_submission_authorized": False,
        "trading_flags_changed": False,
    }

    db_session.refresh(account)
    risk = db_session.scalar(
        select(RiskSetting).where(RiskSetting.exchange_account_id == account.id)
    )
    assert account.trading_enabled is False
    assert risk is not None
    assert risk.trading_enabled is False


def test_phase4_final_release_check_api_records_audit(db_session: Session) -> None:
    owner, account, _, _ = _ready_account(db_session)

    response = record_final_release_check(
        account.id,
        Phase4FinalReleaseCheckRequest(
            max_notional=Decimal("20"),
            dedicated_account_confirmed=True,
            account_empty_confirmed=True,
            withdrawals_disabled_confirmed=True,
            delete_api_key_after_test_confirmed=True,
            first_order_stop_review_confirmed=True,
            no_live_order_submission_confirmed=True,
            acknowledgement=PHASE4_FINAL_RELEASE_CHECK_ACK,
        ),
        current_user=owner,
        db=db_session,
    )

    assert response.exchange_account_id == account.id
    assert response.order_submission_authorized is False
    assert response.trading_flags_changed is False
    assert db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "real.small_fund.final_release_check_recorded")
    ) == 1


def test_phase4_final_release_check_requires_super_admin(db_session: Session) -> None:
    owner, account, _, _ = _ready_account(db_session)
    owner.role = UserRole.ADMIN
    db_session.commit()

    with pytest.raises(Phase4FinalReleaseCheckBlockedError) as error:
        _record_final_check(db_session, owner=owner, account=account)

    assert (
        "super administrator privileges are required for Phase 4 final check"
        in error.value.reasons
    )


def test_phase4_final_release_check_requires_order_window_audit(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    _add_phase4_review_audit(db_session, owner=owner, account=account)

    with pytest.raises(Phase4FinalReleaseCheckBlockedError) as error:
        _record_final_check(db_session, owner=owner, account=account)

    assert "Phase 4 order-window audit is required" in error.value.reasons


def test_phase4_final_release_check_requires_all_confirmations(
    db_session: Session,
) -> None:
    owner, account, _, _ = _ready_account(db_session)

    with pytest.raises(Phase4FinalReleaseCheckBlockedError) as error:
        record_phase4_final_release_check(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            max_notional=Decimal("20"),
            dedicated_account_confirmed=True,
            account_empty_confirmed=False,
            withdrawals_disabled_confirmed=True,
            delete_api_key_after_test_confirmed=True,
            first_order_stop_review_confirmed=True,
            no_live_order_submission_confirmed=True,
            acknowledgement=PHASE4_FINAL_RELEASE_CHECK_ACK,
        )

    assert "empty-account confirmation is required" in error.value.reasons


def test_phase4_final_release_check_blocks_trading_enabled_state(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner, trading_enabled=True)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account, trading_enabled=True)
    _add_phase4_review_audit(db_session, owner=owner, account=account)
    _add_phase4_order_window_audit(db_session, owner=owner, account=account)

    with pytest.raises(Phase4FinalReleaseCheckBlockedError) as error:
        _record_final_check(db_session, owner=owner, account=account)

    assert "exchange account trading_enabled must remain false" in error.value.reasons
    assert "risk settings trading_enabled must remain false" in error.value.reasons
