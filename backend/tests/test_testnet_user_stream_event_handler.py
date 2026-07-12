from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_testnet_order_lifecycle import _submitted_execution

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import Balance, OrderExecutionStatus
from app.services.testnet_user_stream_event_handler import (
    PersistingTestnetUserStreamEventHandler,
)
from app.services.testnet_user_stream_runtime import parse_testnet_user_stream_event


def test_persisting_handler_updates_owned_order_lifecycle(
    db_session: Session,
) -> None:
    user_id, account_id, execution = _submitted_execution(db_session)
    handler = PersistingTestnetUserStreamEventHandler(
        db=db_session,
        user_id=user_id,
        exchange_account_id=account_id,
    )

    result = handler(
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BINANCE,
            payload={
                "e": "executionReport",
                "c": execution.client_order_id,
                "i": 9001,
                "X": "FILLED",
                "z": "0.01",
            },
        )
    )

    db_session.refresh(execution)
    assert result.order_result is not None
    assert result.order_result.transitioned is True
    assert execution.status == OrderExecutionStatus.FILLED


def test_persisting_handler_commits_balance_updates(
    db_session: Session,
) -> None:
    user_id, account_id, _ = _submitted_execution(db_session)
    handler = PersistingTestnetUserStreamEventHandler(
        db=db_session,
        user_id=user_id,
        exchange_account_id=account_id,
    )

    result = handler(
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BINANCE,
            payload={"e": "outboundAccountPosition", "B": [{"a": "USDT", "f": "3", "l": "2"}]},
        )
    )

    balance = db_session.scalar(
        select(Balance).where(
            Balance.user_id == user_id,
            Balance.exchange_account_id == account_id,
            Balance.asset == "USDT",
        )
    )
    assert result.state_event_processed is True
    assert balance is not None
    assert balance.total_quantity == Decimal("5")
