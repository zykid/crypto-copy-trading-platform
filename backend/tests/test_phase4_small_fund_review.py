from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.exchange_accounts import record_small_fund_review
from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import (
    AccountMode,
    ApiKeySecret,
    ExchangeAccount,
    ExchangeName,
)
from app.db.models.observability import AuditLog
from app.db.models.trading import RiskSetting
from app.db.models.user import User, UserRole
from app.schemas.exchange_account import Phase4SmallFundReviewRequest
from app.services.phase4_small_fund_review import (
    PHASE4_SMALL_FUND_REVIEW_ACK,
    Phase4SmallFundReviewBlockedError,
    record_phase4_small_fund_review,
)


def _user(role: UserRole = UserRole.SUPER_ADMIN) -> User:
    return User(
        email="phase4@example.com",
        username="phase4_operator",
        password_hash="hashed",
        role=role,
    )


def _real_okx_account(owner: User, *, trading_enabled: bool = False) -> ExchangeAccount:
    return ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.REAL,
        account_label="OKX production read-only",
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


def _add_api_key_metadata(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
) -> None:
    db_session.add(
        ApiKeySecret(
            user_id=owner.id,
            exchange_account_id=account.id,
            encrypted_api_key=encrypt_secret("production-key"),
            encrypted_api_secret=encrypt_secret("production-secret"),
            encrypted_passphrase=encrypt_secret("production-passphrase"),
        )
    )
    db_session.commit()


def _add_successful_read_only_audit(
    db_session: Session,
    *,
    owner: User,
    account: ExchangeAccount,
) -> AuditLog:
    audit = AuditLog(
        user_id=owner.id,
        exchange_account_id=account.id,
        action="real.read_only.authentication.checked",
        severity="INFO",
        payload={
            "exchange_name": "okx",
            "account_mode": "REAL",
            "authenticated": True,
            "balance_asset_count": 0,
        },
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


def test_phase4_small_fund_review_records_critical_audit_without_authorizing_orders(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    _add_api_key_metadata(db_session, owner=owner, account=account)
    read_only_audit = _add_successful_read_only_audit(
        db_session,
        owner=owner,
        account=account,
    )

    review = record_phase4_small_fund_review(
        db_session,
        user_id=owner.id,
        user_role=owner.role,
        exchange_account_id=account.id,
        max_notional=Decimal("25"),
        acknowledgement=PHASE4_SMALL_FUND_REVIEW_ACK,
    )

    assert review.exchange_account_id == account.id
    assert review.read_only_audit_log_id == read_only_audit.id
    assert review.order_submission_authorized is False
    assert review.trading_flags_changed is False

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "real.small_fund.review_recorded")
    )
    assert audit is not None
    assert audit.id == review.audit_log_id
    assert audit.severity == "CRITICAL"
    assert audit.payload == {
        "exchange_name": "okx",
        "account_mode": "REAL",
        "max_notional": "25",
        "max_notional_cap": "100",
        "acknowledgement": PHASE4_SMALL_FUND_REVIEW_ACK,
        "read_only_audit_log_id": read_only_audit.id,
        "order_submission_authorized": False,
        "trading_flags_changed": False,
    }
    assert "production-key" not in str(audit.payload)
    assert "production-secret" not in str(audit.payload)

    db_session.refresh(account)
    risk = db_session.scalar(
        select(RiskSetting).where(RiskSetting.exchange_account_id == account.id)
    )
    assert account.trading_enabled is False
    assert risk is not None
    assert risk.trading_enabled is False


def test_phase4_small_fund_review_api_records_audit(db_session: Session) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    _add_api_key_metadata(db_session, owner=owner, account=account)
    _add_successful_read_only_audit(db_session, owner=owner, account=account)

    response = record_small_fund_review(
        account.id,
        Phase4SmallFundReviewRequest(
            max_notional=Decimal("50"),
            acknowledgement=PHASE4_SMALL_FUND_REVIEW_ACK,
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
        .where(AuditLog.action == "real.small_fund.review_recorded")
    ) == 1


def test_phase4_small_fund_review_requires_super_admin(db_session: Session) -> None:
    owner = _user(role=UserRole.ADMIN)
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    _add_api_key_metadata(db_session, owner=owner, account=account)
    _add_successful_read_only_audit(db_session, owner=owner, account=account)

    with pytest.raises(Phase4SmallFundReviewBlockedError) as error:
        record_phase4_small_fund_review(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            max_notional=Decimal("25"),
            acknowledgement=PHASE4_SMALL_FUND_REVIEW_ACK,
        )

    assert "super administrator privileges are required" in " ".join(error.value.reasons)
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_phase4_small_fund_review_requires_successful_read_only_audit(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account)
    _add_api_key_metadata(db_session, owner=owner, account=account)

    with pytest.raises(Phase4SmallFundReviewBlockedError) as error:
        record_phase4_small_fund_review(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            max_notional=Decimal("25"),
            acknowledgement=PHASE4_SMALL_FUND_REVIEW_ACK,
        )

    assert "successful REAL read-only authentication audit is required" in error.value.reasons
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_phase4_small_fund_review_blocks_trading_enabled_state(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner, trading_enabled=True)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner=owner, account=account, trading_enabled=True)
    _add_api_key_metadata(db_session, owner=owner, account=account)
    _add_successful_read_only_audit(db_session, owner=owner, account=account)

    with pytest.raises(Phase4SmallFundReviewBlockedError) as error:
        record_phase4_small_fund_review(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            max_notional=Decimal("25"),
            acknowledgement=PHASE4_SMALL_FUND_REVIEW_ACK,
        )

    assert "exchange account trading_enabled must remain false" in error.value.reasons
    assert "risk settings trading_enabled must remain false" in error.value.reasons
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 1
