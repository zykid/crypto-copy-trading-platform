from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    Balance,
    ExchangeAccount,
    ExchangeName,
    Position,
    User,
)
from app.services.testnet_account_state_sync import (
    TestnetAccountStateSyncError as AccountStateSyncError,
)
from app.services.testnet_account_state_sync import (
    TestnetAccountStateSyncStatus as SyncStatus,
)
from app.services.testnet_account_state_sync import sync_testnet_account_state_event
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEvent as UserStreamEvent,
)
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEventType as UserStreamEventType,
)


def create_user_and_account(
    db_session: Session,
    *,
    suffix: str,
    exchange_name: ExchangeName,
    account_mode: AccountMode = AccountMode.TESTNET,
) -> tuple[User, ExchangeAccount]:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        password_hash="hashed-password",
    )
    db_session.add(user)
    db_session.flush()
    account = ExchangeAccount(
        user_id=user.id,
        exchange_name=exchange_name,
        account_mode=account_mode,
        account_label=f"{suffix} account",
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def event(
    *,
    exchange_name: ExchangeName,
    event_type: UserStreamEventType,
    payload: dict[str, object],
) -> UserStreamEvent:
    return UserStreamEvent(
        exchange_name=exchange_name,
        event_type=event_type,
        raw_payload=payload,
    )


def test_sync_binance_balance_event_upserts_absolute_balances(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(
        db_session,
        suffix="binance",
        exchange_name=ExchangeName.BINANCE,
    )
    balance_event = event(
        exchange_name=ExchangeName.BINANCE,
        event_type=UserStreamEventType.BALANCE,
        payload={
            "e": "outboundAccountPosition",
            "B": [
                {"a": "BTC", "f": "1.25", "l": "0.25"},
                {"a": "USDT", "f": "100", "l": "5"},
            ],
        },
    )

    result = sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=balance_event,
    )

    balances = db_session.scalars(select(Balance).order_by(Balance.asset)).all()
    assert result.status == SyncStatus.SYNCED
    assert result.balances_synced == 2
    assert [(item.asset, item.total_quantity) for item in balances] == [
        ("BTC", Decimal("1.5000000000")),
        ("USDT", Decimal("105.0000000000")),
    ]

    updated_event = event(
        exchange_name=ExchangeName.BINANCE,
        event_type=UserStreamEventType.BALANCE,
        payload={"B": [{"a": "BTC", "f": "2", "l": "0"}]},
    )
    sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=updated_event,
    )

    btc = db_session.scalar(select(Balance).where(Balance.asset == "BTC"))
    assert btc is not None
    assert btc.available_quantity == Decimal("2")
    assert btc.locked_quantity == Decimal("0")
    assert btc.total_quantity == Decimal("2")
    assert len(db_session.scalars(select(Balance)).all()) == 2


def test_sync_bybit_position_event_applies_signed_quantity(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(
        db_session,
        suffix="bybit",
        exchange_name=ExchangeName.BYBIT,
    )
    position_event = event(
        exchange_name=ExchangeName.BYBIT,
        event_type=UserStreamEventType.POSITION,
        payload={
            "topic": "position",
            "data": [
                {"symbol": "BTCUSDT", "side": "Buy", "size": "0.7"},
                {"symbol": "ETHUSDT", "side": "Sell", "size": "2"},
            ],
        },
    )

    result = sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=position_event,
    )

    positions = db_session.scalars(select(Position).order_by(Position.symbol)).all()
    assert result.positions_synced == 2
    assert [(item.symbol, item.quantity) for item in positions] == [
        ("BTCUSDT", Decimal("0.7000000000")),
        ("ETHUSDT", Decimal("-2.0000000000")),
    ]


def test_sync_okx_balance_and_position_events(db_session: Session) -> None:
    user, account = create_user_and_account(
        db_session,
        suffix="okx",
        exchange_name=ExchangeName.OKX,
    )
    balance_event = event(
        exchange_name=ExchangeName.OKX,
        event_type=UserStreamEventType.BALANCE,
        payload={
            "arg": {"channel": "account"},
            "data": [
                {
                    "details": [
                        {
                            "ccy": "USDT",
                            "availBal": "90",
                            "frozenBal": "10",
                            "cashBal": "100",
                        }
                    ]
                }
            ],
        },
    )
    position_event = event(
        exchange_name=ExchangeName.OKX,
        event_type=UserStreamEventType.POSITION,
        payload={
            "arg": {"channel": "positions"},
            "data": [{"instId": "BTC-USDT-SWAP", "pos": "-0.5"}],
        },
    )

    balance_result = sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=balance_event,
    )
    position_result = sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=position_event,
    )

    balance = db_session.scalars(select(Balance)).one()
    position = db_session.scalars(select(Position)).one()
    assert balance_result.balances_synced == 1
    assert position_result.positions_synced == 1
    assert balance.total_quantity == Decimal("100")
    assert position.symbol == "BTC-USDT-SWAP"
    assert position.quantity == Decimal("-0.5")


def test_sync_rejects_cross_tenant_account_access(db_session: Session) -> None:
    owner, account = create_user_and_account(
        db_session,
        suffix="owner",
        exchange_name=ExchangeName.BINANCE,
    )
    other, _ = create_user_and_account(
        db_session,
        suffix="other",
        exchange_name=ExchangeName.BINANCE,
    )
    balance_event = event(
        exchange_name=ExchangeName.BINANCE,
        event_type=UserStreamEventType.BALANCE,
        payload={"B": [{"a": "BTC", "f": "1", "l": "0"}]},
    )

    with pytest.raises(AccountStateSyncError, match="was not found"):
        sync_testnet_account_state_event(
            db_session,
            user_id=other.id,
            exchange_account_id=account.id,
            event=balance_event,
        )

    assert owner.id != other.id
    assert db_session.scalars(select(Balance)).all() == []


def test_sync_rejects_non_testnet_and_wrong_exchange_accounts(
    db_session: Session,
) -> None:
    simulation_user, simulation_account = create_user_and_account(
        db_session,
        suffix="simulation",
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.SIMULATION,
    )
    testnet_user, testnet_account = create_user_and_account(
        db_session,
        suffix="wrong-exchange",
        exchange_name=ExchangeName.BYBIT,
    )
    balance_event = event(
        exchange_name=ExchangeName.BINANCE,
        event_type=UserStreamEventType.BALANCE,
        payload={"B": [{"a": "BTC", "f": "1", "l": "0"}]},
    )

    with pytest.raises(AccountStateSyncError, match="account mode must be TESTNET"):
        sync_testnet_account_state_event(
            db_session,
            user_id=simulation_user.id,
            exchange_account_id=simulation_account.id,
            event=balance_event,
        )
    with pytest.raises(AccountStateSyncError, match="does not match account"):
        sync_testnet_account_state_event(
            db_session,
            user_id=testnet_user.id,
            exchange_account_id=testnet_account.id,
            event=balance_event,
        )

    assert db_session.scalars(select(Balance)).all() == []


def test_invalid_multi_balance_event_is_atomic(db_session: Session) -> None:
    user, account = create_user_and_account(
        db_session,
        suffix="atomic",
        exchange_name=ExchangeName.BINANCE,
    )
    invalid_event = event(
        exchange_name=ExchangeName.BINANCE,
        event_type=UserStreamEventType.BALANCE,
        payload={
            "B": [
                {"a": "BTC", "f": "1", "l": "0"},
                {"a": "USDT", "f": "not-a-number", "l": "0"},
            ]
        },
    )

    with pytest.raises(AccountStateSyncError, match="free must be numeric"):
        sync_testnet_account_state_event(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            event=invalid_event,
        )

    assert db_session.scalars(select(Balance)).all() == []


def test_order_and_unknown_events_do_not_write_account_state(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(
        db_session,
        suffix="ignored",
        exchange_name=ExchangeName.BYBIT,
    )
    order_event = event(
        exchange_name=ExchangeName.BYBIT,
        event_type=UserStreamEventType.ORDER,
        payload={"topic": "order", "data": []},
    )

    result = sync_testnet_account_state_event(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        event=order_event,
    )

    assert result.status == SyncStatus.IGNORED
    assert db_session.scalars(select(Balance)).all() == []
    assert db_session.scalars(select(Position)).all() == []
