from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import AccountMode, ApiKeySecret, ExchangeAccount, ExchangeName
from app.db.models.trading import RiskSetting
from app.db.models.user import User
from app.services.testnet_order_window import (
    OrderWindowPlanStatus,
    build_testnet_order_window_plan,
)


def user(email: str, username: str) -> User:
    return User(email=email, username=username, password_hash="hashed")


def add_account(
    db_session: Session,
    *,
    owner: User,
    mode: AccountMode = AccountMode.TESTNET,
) -> ExchangeAccount:
    account = ExchangeAccount(
        user_id=owner.id,
        exchange_name=ExchangeName.BINANCE,
        account_mode=mode,
        account_label="binance testnet",
        trading_enabled=False,
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
            trading_enabled=False,
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


def test_testnet_order_window_plan_is_ready_without_authorizing_orders(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_risk_settings(db_session, owner=owner, account=account)
    add_api_key_metadata(db_session, owner=owner, account=account)

    plan = build_testnet_order_window_plan(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=False,
    )

    assert plan.status == OrderWindowPlanStatus.READY_FOR_SEPARATE_APPROVAL
    assert plan.mutations_allowed is False
    assert plan.order_submission_authorized is False
    assert plan.blocked_reasons == ()
    assert plan.state.exchange_account_trading_enabled is False
    assert plan.state.risk_trading_enabled is False
    assert "restore TESTNET_ADAPTERS_ENABLED=false" in " ".join(plan.required_operator_steps)


def test_testnet_order_window_plan_blocks_missing_prerequisites(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner, mode=AccountMode.SIMULATION)

    plan = build_testnet_order_window_plan(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=False,
    )

    assert plan.status == OrderWindowPlanStatus.BLOCKED
    assert "account mode must be TESTNET before preparing an order window" in plan.blocked_reasons
    assert "risk settings must exist before preparing an order window" in plan.blocked_reasons
    assert (
        "encrypted API key metadata must exist before preparing an order window"
        in plan.blocked_reasons
    )
    assert plan.mutations_allowed is False
    assert plan.order_submission_authorized is False


def test_testnet_order_window_plan_does_not_create_risk_settings(
    db_session: Session,
) -> None:
    owner = user("owner@example.com", "owner")
    db_session.add(owner)
    db_session.commit()
    account = add_account(db_session, owner=owner)
    add_api_key_metadata(db_session, owner=owner, account=account)

    build_testnet_order_window_plan(
        db_session,
        user_id=owner.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=False,
    )

    risk_setting_count = db_session.scalar(select(func.count()).select_from(RiskSetting))
    assert risk_setting_count == 0
