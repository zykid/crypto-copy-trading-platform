import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import AccountMode, ApiKeySecret, ExchangeAccount, ExchangeName
from app.db.models.trading import RiskSetting
from app.db.models.user import User
from app.services.testnet_order_admission import (
    TestnetOrderAdmissionStatus,
    build_testnet_order_admission_report,
)


def user(email: str, username: str) -> User:
    return User(email=email, username=username, password_hash="hashed")


def add_account(
    db_session: Session,
    *,
    owner: User,
    trading_enabled: bool = False,
    mode: AccountMode = AccountMode.TESTNET,
) -> ExchangeAccount:
    account = ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.BINANCE,
        account_mode=mode,
        account_label="binance testnet",
        trading_enabled=trading_enabled,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def add_risk_settings(
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


def add_api_key_metadata(db_session: Session, *, owner: User, account: ExchangeAccount) -> None:
    db_session.add(
        ApiKeySecret(
            user_id=owner.id,
            exchange_account_id=account.id,
            encrypted_api_key=encrypt_secret("testnet-api-key"),
            encrypted_api_secret=encrypt_secret("testnet-api-secret"),
            encrypted_passphrase=encrypt_secret("testnet-passphrase"),
        )
    )
    db_session.commit()


def checks_by_name(report):
    return {check.name: check for check in report.checks}


def test_pre_window_testnet_order_admission_passes_without_authorizing_orders(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    report = build_testnet_order_admission_report(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=False,
    )

    assert report.overall_status == TestnetOrderAdmissionStatus.PASS
    assert report.read_only is True
    assert report.order_submission_authorized is False
    assert all(check.status == TestnetOrderAdmissionStatus.PASS for check in report.checks)
    assert "TESTNET_ADAPTERS_ENABLED must be true before testnet orders" in report.gate_reasons
    assert (
        "exchange account trading_enabled must be true before testnet orders"
        in report.gate_reasons
    )
    assert "risk settings trading_enabled must be true before testnet orders" in report.gate_reasons
    assert "manual testnet order enable confirmation must be recorded" in report.gate_reasons


def test_pre_window_testnet_order_admission_blocks_enabled_runtime_state(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner, trading_enabled=True)
    add_risk_settings(db_session, owner=owner, account=account, trading_enabled=True)
    add_api_key_metadata(db_session, owner=owner, account=account)

    report = build_testnet_order_admission_report(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=True,
    )

    checks = checks_by_name(report)
    assert report.overall_status == TestnetOrderAdmissionStatus.BLOCKED
    assert report.order_submission_authorized is False
    assert (
        checks["testnet_adapters_disabled_before_window"].status
        == TestnetOrderAdmissionStatus.BLOCKED
    )
    assert (
        checks["exchange_account_trading_disabled_before_window"].status
        == TestnetOrderAdmissionStatus.BLOCKED
    )
    assert (
        checks["risk_trading_disabled_before_window"].status
        == TestnetOrderAdmissionStatus.BLOCKED
    )


def test_pre_window_testnet_order_admission_does_not_create_missing_risk_settings(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_api_key_metadata(db_session, owner=owner, account=account)

    report = build_testnet_order_admission_report(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=False,
    )

    risk_setting_count = db_session.scalar(select(func.count()).select_from(RiskSetting))
    checks = checks_by_name(report)
    assert risk_setting_count == 0
    assert report.overall_status == TestnetOrderAdmissionStatus.BLOCKED
    assert checks["risk_settings_exist"].status == TestnetOrderAdmissionStatus.BLOCKED


def test_pre_window_testnet_order_admission_requires_owned_account(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    other = user("other@example.com", "other")
    db_session.add_all([owner, other])
    db_session.commit()
    account = add_account(db_session, owner=owner)

    with pytest.raises(ValueError, match="account not found"):
        build_testnet_order_admission_report(
            db_session,
            user_id=other.id,
            exchange_account_id=account.id,
            testnet_adapters_enabled=False,
        )
