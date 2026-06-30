from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import (
    AccountMode,
    ApiKeySecret,
    ExchangeAccount,
    ExchangeName,
)
from app.db.models.trading import RiskSetting
from app.db.models.user import User, UserRole
from app.services.phase4_readiness import (
    Phase4ReadinessStatus,
    build_phase4_readiness_report,
)


def _user(*, role: UserRole = UserRole.SUPER_ADMIN, mfa_enabled: bool = True) -> User:
    return User(
        email="operator@example.com",
        username="operator",
        password_hash="hashed",
        role=role,
        mfa_enabled=mfa_enabled,
    )


def _real_okx_account(owner: User, *, trading_enabled: bool = False) -> ExchangeAccount:
    return ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.REAL,
        account_label="okx real read only",
        trading_enabled=trading_enabled,
    )


def _add_risk_settings(db: Session, owner: User, account: ExchangeAccount) -> None:
    db.add(
        RiskSetting(
            user_id=owner.id,
            exchange_account_id=account.id,
            trading_enabled=False,
            blocked_symbols=[],
        )
    )
    db.commit()


def _add_api_key_metadata(db: Session, owner: User, account: ExchangeAccount) -> None:
    db.add(
        ApiKeySecret(
            user_id=owner.id,
            exchange_account_id=account.id,
            encrypted_api_key=encrypt_secret("real-key"),
            encrypted_api_secret=encrypt_secret("real-secret"),
            encrypted_passphrase=encrypt_secret("real-passphrase"),
        )
    )
    db.commit()


def _checks_by_name(report):
    return {check.name: check for check in report.checks}


def test_phase4_readiness_passes_without_authorizing_orders(db_session: Session) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_risk_settings(db_session, owner, account)
    _add_api_key_metadata(db_session, owner, account)

    report = build_phase4_readiness_report(
        db_session,
        user=owner,
        exchange_account_id=account.id,
    )

    assert report.overall_status == Phase4ReadinessStatus.PASS
    assert report.read_only is True
    assert report.order_submission_authorized is False
    assert report.gate_reasons == ()
    assert "real-secret" not in str(report)


def test_phase4_readiness_blocks_when_mfa_or_risk_is_missing(
    db_session: Session,
) -> None:
    owner = _user(mfa_enabled=False)
    db_session.add(owner)
    db_session.commit()
    account = _real_okx_account(owner)
    db_session.add(account)
    db_session.commit()
    _add_api_key_metadata(db_session, owner, account)

    report = build_phase4_readiness_report(
        db_session,
        user=owner,
        exchange_account_id=account.id,
    )

    checks = _checks_by_name(report)
    assert report.overall_status == Phase4ReadinessStatus.BLOCKED
    assert checks["operator_mfa_enabled"].status == Phase4ReadinessStatus.BLOCKED
    assert checks["risk_settings_exist"].status == Phase4ReadinessStatus.BLOCKED
    assert checks["risk_trading_disabled"].status == Phase4ReadinessStatus.BLOCKED


def test_phase4_readiness_blocks_non_real_or_trading_enabled_account(
    db_session: Session,
) -> None:
    owner = _user()
    db_session.add(owner)
    db_session.commit()
    account = ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.TESTNET,
        account_label="okx demo",
        trading_enabled=True,
    )
    db_session.add(account)
    db_session.commit()

    report = build_phase4_readiness_report(
        db_session,
        user=owner,
        exchange_account_id=account.id,
    )

    checks = _checks_by_name(report)
    assert checks["account_is_real_okx"].status == Phase4ReadinessStatus.BLOCKED
    assert checks["exchange_trading_disabled"].status == Phase4ReadinessStatus.BLOCKED
