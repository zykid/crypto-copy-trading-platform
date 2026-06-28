from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import (
    AccountMode,
    ApiKeySecret,
    ExchangeAccount,
    ExchangeName,
)
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderSide, RiskSetting
from app.db.models.user import User, UserRole
from app.services.testnet_order_window_approval import (
    TESTNET_ORDER_WINDOW_APPROVAL_ACK,
    TestnetOrderWindowApprovalBlockedError,
    record_testnet_order_window_approval,
)


def user(email: str, username: str, role: UserRole = UserRole.SUPER_ADMIN) -> User:
    return User(email=email, username=username, password_hash="hashed", role=role)


def add_account(
    db_session: Session,
    *,
    owner: User,
    mode: AccountMode = AccountMode.TESTNET,
    trading_enabled: bool = False,
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


def test_testnet_order_window_approval_writes_audit_without_authorizing_orders(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    approval = record_testnet_order_window_approval(
        db_session,
        user_id=owner.id,
        user_role=owner.role,
        exchange_account_id=account.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        max_quantity=Decimal("0.001"),
        max_notional=Decimal("100"),
        duration_minutes=5,
        acknowledgement=TESTNET_ORDER_WINDOW_APPROVAL_ACK,
        testnet_adapters_enabled=False,
    )

    assert approval.exchange_account_id == account.id
    assert approval.order_submission_authorized is False
    assert approval.trading_flags_changed is False

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "testnet.order_window.approval_recorded")
    )
    assert audit is not None
    assert audit.id == approval.audit_log_id
    assert audit.severity == "WARNING"
    assert audit.payload == {
        "exchange_name": "binance",
        "account_mode": "TESTNET",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "max_quantity": "0.001",
        "max_notional": "100",
        "duration_minutes": 5,
        "acknowledgement": TESTNET_ORDER_WINDOW_APPROVAL_ACK,
        "order_submission_authorized": False,
        "trading_flags_changed": False,
    }
    assert "testnet-api-key" not in str(audit.payload)
    assert "testnet-api-secret" not in str(audit.payload)

    db_session.refresh(account)
    risk = db_session.scalar(
        select(RiskSetting).where(RiskSetting.exchange_account_id == account.id)
    )
    assert account.trading_enabled is False
    assert risk is not None
    assert risk.trading_enabled is False


def test_testnet_order_window_approval_requires_admin_role(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner", role=UserRole.NORMAL_USER)
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    with pytest.raises(TestnetOrderWindowApprovalBlockedError) as error:
        record_testnet_order_window_approval(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            max_quantity=Decimal("0.001"),
            max_notional=Decimal("100"),
            duration_minutes=5,
            acknowledgement=TESTNET_ORDER_WINDOW_APPROVAL_ACK,
            testnet_adapters_enabled=False,
        )

    assert (
        "admin privileges are required to approve a testnet order window"
        in error.value.reasons
    )
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_testnet_order_window_approval_blocks_real_accounts(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner, mode=AccountMode.REAL)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    with pytest.raises(TestnetOrderWindowApprovalBlockedError) as error:
        record_testnet_order_window_approval(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            max_quantity=Decimal("0.001"),
            max_notional=Decimal("100"),
            duration_minutes=5,
            acknowledgement=TESTNET_ORDER_WINDOW_APPROVAL_ACK,
            testnet_adapters_enabled=False,
        )

    assert "account mode must be TESTNET before approving an order window" in error.value.reasons
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_testnet_order_window_approval_requires_pre_window_disabled_state(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner, trading_enabled=True)
    add_risk_settings(db_session, owner=owner, account=account, trading_enabled=True)
    add_api_key_metadata(db_session, owner=owner, account=account)

    with pytest.raises(TestnetOrderWindowApprovalBlockedError) as error:
        record_testnet_order_window_approval(
            db_session,
            user_id=owner.id,
            user_role=owner.role,
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            max_quantity=Decimal("0.001"),
            max_notional=Decimal("100"),
            duration_minutes=5,
            acknowledgement=TESTNET_ORDER_WINDOW_APPROVAL_ACK,
            testnet_adapters_enabled=True,
        )

    assert (
        "TESTNET_ADAPTERS_ENABLED must still be false before approval is recorded"
        in error.value.reasons
    )
    assert (
        "exchange account trading_enabled must still be false before approval"
        in error.value.reasons
    )
    assert (
        "risk settings trading_enabled must still be false before approval"
        in error.value.reasons
    )
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
