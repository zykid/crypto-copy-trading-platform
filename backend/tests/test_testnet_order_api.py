from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import AccountMode, ApiKeySecret, ExchangeAccount, ExchangeName
from app.db.models.trading import OrderSide, OrderType, RiskSetting
from app.db.models.user import User
from app.schemas.trading import TestnetOrderSubmitRequest
from app.services.exchange_accounts import get_exchange_credentials
from app.services.testnet_order_api import (
    TestnetOrderApiBlockedError,
    build_testnet_order_api_context,
)


def user(email: str, username: str) -> User:
    return User(email=email, username=username, password_hash="hashed")


def payload(account_id: str, *, confirmed: bool = True) -> TestnetOrderSubmitRequest:
    return TestnetOrderSubmitRequest(
        exchange_account_id=account_id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        client_order_id="testnet-client-1",
        manual_testnet_order_enable_confirmed=confirmed,
    )


def add_account(
    db_session: Session,
    *,
    owner: User,
    mode: AccountMode = AccountMode.TESTNET,
    trading_enabled: bool = True,
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


def add_risk_settings(db_session: Session, *, owner: User, account: ExchangeAccount) -> None:
    db_session.add(
        RiskSetting(
            user_id=owner.id,
            exchange_account_id=account.id,
            trading_enabled=True,
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


def test_exchange_credentials_are_loaded_only_for_the_owning_user(db_session: Session) -> None:
    owner = user("owner@example.com", "owner")
    other = user("other@example.com", "other")
    db_session.add_all([owner, other])
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_api_key_metadata(db_session, owner=owner, account=account)

    credentials = get_exchange_credentials(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
    )
    other_credentials = get_exchange_credentials(
        db_session,
        user_id=other.id,
        exchange_account_id=account.id,
    )

    assert credentials is not None
    assert credentials.api_key == "testnet-api-key"
    assert credentials.api_secret == "testnet-api-secret"
    assert credentials.passphrase == "testnet-passphrase"
    assert other_credentials is None


def test_testnet_order_api_context_requires_owned_account(db_session: Session) -> None:
    owner = user("owner@example.com", "owner")
    other = user("other@example.com", "other")
    db_session.add_all([owner, other])
    db_session.commit()
    account = add_account(db_session, owner=owner)

    with pytest.raises(ValueError, match="account not found"):
        build_testnet_order_api_context(
            db_session,
            user_id=other.id,
            payload=payload(account.id),
            testnet_adapters_enabled=True,
        )


def test_testnet_order_api_context_blocks_when_gate_conditions_fail(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(
        db_session,
        owner=owner,
        mode=AccountMode.SIMULATION,
        trading_enabled=False,
    )

    with pytest.raises(TestnetOrderApiBlockedError) as exc_info:
        build_testnet_order_api_context(
            db_session,
            user_id=owner.id,
            payload=payload(account.id, confirmed=False),
            testnet_adapters_enabled=False,
        )

    reasons = exc_info.value.reasons
    assert "account mode must be TESTNET before testnet orders" in reasons
    assert "TESTNET_ADAPTERS_ENABLED must be true before testnet orders" in reasons
    assert "exchange account trading_enabled must be true before testnet orders" in reasons
    assert "risk settings trading_enabled must be true before testnet orders" in reasons
    assert "testnet API key metadata must be configured before testnet orders" in reasons
    assert "manual testnet order enable confirmation must be recorded" in reasons


def test_testnet_order_api_context_builds_order_after_all_gate_conditions_pass(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    context = build_testnet_order_api_context(
        db_session,
        user_id=owner.id,
        payload=payload(account.id),
        testnet_adapters_enabled=True,
    )

    assert context.account.id == account.id
    assert context.gate_result.approved is True
    assert context.order.exchange_name == ExchangeName.BINANCE
    assert context.order.client_order_id == "testnet-client-1"
    assert context.credentials.api_key == "testnet-api-key"
    assert context.credentials.api_secret == "testnet-api-secret"
    assert not hasattr(context.order, "api_secret")
