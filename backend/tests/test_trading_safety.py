from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import OrderExecutionStatus, OrderSide, OrderType, RiskSetting
from app.services.exchange_accounts import create_account, get_owned_account, upsert_api_key_secret
from app.services.order_engine import execute_signal_for_account
from app.services.position_engine import apply_fill, get_or_create_position
from app.services.risk_engine import RiskOrderInput, check_order_risk, get_or_create_risk_settings
from app.services.signal_engine import create_manual_signal
from app.services.users import create_user


def create_test_user(db: Session, suffix: str):
    return create_user(
        db,
        email=f"user-{suffix}@example.com",
        username=f"user_{suffix}",
        password="ChangeMe12345!",
    )


def create_mock_account(db: Session, user_id: str, *, trading_enabled: bool = True):
    return create_account(
        db,
        user_id=user_id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "Mock Simulation",
            "trading_enabled": trading_enabled,
        },
    )


def test_owned_account_lookup_enforces_user_id(db_session: Session) -> None:
    owner = create_test_user(db_session, "owner")
    other = create_test_user(db_session, "other")
    account = create_mock_account(db_session, owner.id)

    assert get_owned_account(db_session, user_id=owner.id, account_id=account.id) is not None
    assert get_owned_account(db_session, user_id=other.id, account_id=account.id) is None


def test_api_key_secret_is_encrypted_at_rest(db_session: Session) -> None:
    user = create_test_user(db_session, "secret")
    account = create_mock_account(db_session, user.id)

    secret = upsert_api_key_secret(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        api_key="plain-api-key",
        api_secret="plain-api-secret",
        passphrase="plain-passphrase",
    )

    assert secret.encrypted_api_key != "plain-api-key"
    assert secret.encrypted_api_secret != "plain-api-secret"
    assert secret.encrypted_passphrase != "plain-passphrase"


def test_default_risk_settings_reject_order(db_session: Session) -> None:
    user = create_test_user(db_session, "risk")
    account = create_mock_account(db_session, user.id, trading_enabled=True)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )

    result = check_order_risk(
        account=account,
        settings=settings,
        order=RiskOrderInput(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            price=Decimal("100"),
        ),
    )

    assert result.decision.value == "REJECTED"
    assert "risk settings trading is disabled" in result.reasons


def test_execute_signal_is_idempotent_for_same_account(db_session: Session) -> None:
    user = create_test_user(db_session, "idempotent")
    account = create_mock_account(db_session, user.id, trading_enabled=True)
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=None,
        quantity=Decimal("0.1"),
        target_position_quantity=None,
    )

    first = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
    )
    second = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
    )

    assert first.id == second.id
    assert first.execution_id == second.execution_id
    assert first.client_order_id == second.client_order_id
    assert first.status == OrderExecutionStatus.FAILED


def test_position_target_executes_delta_not_full_target(db_session: Session) -> None:
    user = create_test_user(db_session, "position")
    account = create_mock_account(db_session, user.id, trading_enabled=True)
    db_session.add(
        RiskSetting(
            user_id=user.id,
            exchange_account_id=account.id,
            trading_enabled=True,
            blocked_symbols=[],
        )
    )
    db_session.commit()
    apply_fill(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.7"),
    )
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=None,
        quantity=None,
        target_position_quantity=Decimal("1.0"),
    )

    execution = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
    )
    position = get_or_create_position(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        symbol="BTCUSDT",
    )

    assert execution.status == OrderExecutionStatus.FILLED
    assert execution.quantity == Decimal("0.3000000000")
    assert position.quantity == Decimal("1.0000000000")
