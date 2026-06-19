from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeAccount, ExchangeName
from app.db.models.trading import Balance, Position
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEvent,
    TestnetUserStreamEventType,
)


class TestnetAccountStateSyncError(RuntimeError):
    pass


class TestnetAccountStateSyncStatus(StrEnum):
    IGNORED = "IGNORED"
    SYNCED = "SYNCED"


@dataclass(frozen=True)
class BalanceStateUpdate:
    asset: str
    available_quantity: Decimal
    locked_quantity: Decimal
    total_quantity: Decimal


@dataclass(frozen=True)
class PositionStateUpdate:
    symbol: str
    quantity: Decimal


@dataclass(frozen=True)
class TestnetAccountStateSyncResult:
    status: TestnetAccountStateSyncStatus
    balances_synced: int
    positions_synced: int


def sync_testnet_account_state_event(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    event: TestnetUserStreamEvent,
) -> TestnetAccountStateSyncResult:
    _require_testnet_account(
        db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
        exchange_name=event.exchange_name,
    )
    if event.event_type == TestnetUserStreamEventType.BALANCE:
        updates = _balance_updates(event.exchange_name, event.raw_payload)
        for update in updates:
            _upsert_balance(
                db,
                user_id=user_id,
                exchange_account_id=exchange_account_id,
                update=update,
            )
        db.flush()
        return TestnetAccountStateSyncResult(
            status=TestnetAccountStateSyncStatus.SYNCED,
            balances_synced=len(updates),
            positions_synced=0,
        )
    if event.event_type == TestnetUserStreamEventType.POSITION:
        updates = _position_updates(event.exchange_name, event.raw_payload)
        for update in updates:
            _upsert_position(
                db,
                user_id=user_id,
                exchange_account_id=exchange_account_id,
                update=update,
            )
        db.flush()
        return TestnetAccountStateSyncResult(
            status=TestnetAccountStateSyncStatus.SYNCED,
            balances_synced=0,
            positions_synced=len(updates),
        )
    return TestnetAccountStateSyncResult(
        status=TestnetAccountStateSyncStatus.IGNORED,
        balances_synced=0,
        positions_synced=0,
    )


def _require_testnet_account(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    exchange_name: ExchangeName,
) -> ExchangeAccount:
    account = db.scalar(
        select(ExchangeAccount).where(
            ExchangeAccount.id == exchange_account_id,
            ExchangeAccount.user_id == user_id,
        )
    )
    if account is None:
        raise TestnetAccountStateSyncError("testnet exchange account was not found")
    if not account.is_active:
        raise TestnetAccountStateSyncError("testnet exchange account is inactive")
    if account.account_mode != AccountMode.TESTNET:
        raise TestnetAccountStateSyncError("account mode must be TESTNET")
    if account.exchange_name != exchange_name:
        raise TestnetAccountStateSyncError("event exchange does not match account")
    return account


def _balance_updates(
    exchange_name: ExchangeName,
    payload: dict[str, Any],
) -> tuple[BalanceStateUpdate, ...]:
    if exchange_name == ExchangeName.BINANCE:
        updates = _binance_balance_updates(payload)
    elif exchange_name == ExchangeName.BYBIT:
        updates = _bybit_balance_updates(payload)
    elif exchange_name == ExchangeName.OKX:
        updates = _okx_balance_updates(payload)
    else:
        raise TestnetAccountStateSyncError("balance event exchange is not supported")
    _require_unique_keys((update.asset for update in updates), label="asset")
    if not updates:
        raise TestnetAccountStateSyncError("balance event contains no balances")
    return updates


def _position_updates(
    exchange_name: ExchangeName,
    payload: dict[str, Any],
) -> tuple[PositionStateUpdate, ...]:
    if exchange_name == ExchangeName.BYBIT:
        updates = _bybit_position_updates(payload)
    elif exchange_name == ExchangeName.OKX:
        updates = _okx_position_updates(payload)
    else:
        raise TestnetAccountStateSyncError("position event exchange is not supported")
    _require_unique_keys((update.symbol for update in updates), label="symbol")
    if not updates:
        raise TestnetAccountStateSyncError("position event contains no positions")
    return updates


def _binance_balance_updates(
    payload: dict[str, Any],
) -> tuple[BalanceStateUpdate, ...]:
    balances = _dict_list(payload.get("B"), field="B")
    updates = []
    for balance in balances:
        available = _quantity(balance.get("f"), field="free", nonnegative=True)
        locked = _quantity(balance.get("l"), field="locked", nonnegative=True)
        updates.append(
            BalanceStateUpdate(
                asset=_identifier(balance.get("a"), field="asset"),
                available_quantity=available,
                locked_quantity=locked,
                total_quantity=available + locked,
            )
        )
    return tuple(updates)


def _bybit_balance_updates(
    payload: dict[str, Any],
) -> tuple[BalanceStateUpdate, ...]:
    updates = []
    for account in _dict_list(payload.get("data"), field="data"):
        for coin in _dict_list(account.get("coin"), field="coin"):
            total = _quantity(
                coin.get("walletBalance"),
                field="walletBalance",
                nonnegative=True,
            )
            locked = _quantity(
                coin.get("locked", "0"),
                field="locked",
                nonnegative=True,
            )
            if locked > total:
                raise TestnetAccountStateSyncError("locked balance exceeds total balance")
            updates.append(
                BalanceStateUpdate(
                    asset=_identifier(coin.get("coin"), field="coin"),
                    available_quantity=total - locked,
                    locked_quantity=locked,
                    total_quantity=total,
                )
            )
    return tuple(updates)


def _okx_balance_updates(
    payload: dict[str, Any],
) -> tuple[BalanceStateUpdate, ...]:
    updates = []
    for account in _dict_list(payload.get("data"), field="data"):
        for detail in _dict_list(account.get("details"), field="details"):
            available = _quantity(
                detail.get("availBal"),
                field="availBal",
                nonnegative=True,
            )
            locked = _quantity(
                detail.get("frozenBal", "0"),
                field="frozenBal",
                nonnegative=True,
            )
            total = _quantity(
                detail.get("cashBal"),
                field="cashBal",
                nonnegative=True,
            )
            if available + locked > total:
                raise TestnetAccountStateSyncError(
                    "available and locked balance exceed total balance"
                )
            updates.append(
                BalanceStateUpdate(
                    asset=_identifier(detail.get("ccy"), field="ccy"),
                    available_quantity=available,
                    locked_quantity=locked,
                    total_quantity=total,
                )
            )
    return tuple(updates)


def _bybit_position_updates(
    payload: dict[str, Any],
) -> tuple[PositionStateUpdate, ...]:
    updates = []
    for position in _dict_list(payload.get("data"), field="data"):
        size = _quantity(position.get("size"), field="size", nonnegative=True)
        side = position.get("side")
        if side == "Buy":
            quantity = size
        elif side == "Sell":
            quantity = -size
        elif side in {"", None} and size == 0:
            quantity = Decimal("0")
        else:
            raise TestnetAccountStateSyncError("Bybit position side is invalid")
        updates.append(
            PositionStateUpdate(
                symbol=_identifier(position.get("symbol"), field="symbol"),
                quantity=quantity,
            )
        )
    return tuple(updates)


def _okx_position_updates(
    payload: dict[str, Any],
) -> tuple[PositionStateUpdate, ...]:
    return tuple(
        PositionStateUpdate(
            symbol=_identifier(position.get("instId"), field="instId"),
            quantity=_quantity(position.get("pos"), field="pos"),
        )
        for position in _dict_list(payload.get("data"), field="data")
    )


def _upsert_balance(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    update: BalanceStateUpdate,
) -> None:
    balance = db.scalar(
        select(Balance).where(
            Balance.user_id == user_id,
            Balance.exchange_account_id == exchange_account_id,
            Balance.asset == update.asset,
        )
    )
    if balance is None:
        balance = Balance(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            asset=update.asset,
        )
        db.add(balance)
    balance.available_quantity = update.available_quantity
    balance.locked_quantity = update.locked_quantity
    balance.total_quantity = update.total_quantity


def _upsert_position(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    update: PositionStateUpdate,
) -> None:
    position = db.scalar(
        select(Position).where(
            Position.user_id == user_id,
            Position.exchange_account_id == exchange_account_id,
            Position.symbol == update.symbol,
        )
    )
    if position is None:
        position = Position(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            symbol=update.symbol,
        )
        db.add(position)
    position.quantity = update.quantity


def _dict_list(value: object, *, field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TestnetAccountStateSyncError(f"{field} must be a list of objects")
    return tuple(value)


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise TestnetAccountStateSyncError(f"{field} must be a string")
    normalized = value.strip().upper()
    if not normalized or len(normalized) > 40:
        raise TestnetAccountStateSyncError(f"{field} is invalid")
    if not all(character.isalnum() or character in {"-", "_"} for character in normalized):
        raise TestnetAccountStateSyncError(f"{field} is invalid")
    return normalized


def _quantity(
    value: object,
    *,
    field: str,
    nonnegative: bool = False,
) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TestnetAccountStateSyncError(f"{field} must be numeric") from exc
    if not quantity.is_finite():
        raise TestnetAccountStateSyncError(f"{field} must be finite")
    if quantity.as_tuple().exponent < -10:
        raise TestnetAccountStateSyncError(f"{field} exceeds database precision")
    if quantity != 0 and quantity.adjusted() >= 18:
        raise TestnetAccountStateSyncError(f"{field} exceeds database precision")
    if nonnegative and quantity < 0:
        raise TestnetAccountStateSyncError(f"{field} must not be negative")
    return quantity


def _require_unique_keys(keys: object, *, label: str) -> None:
    values = tuple(keys)
    if len(values) != len(set(values)):
        raise TestnetAccountStateSyncError(f"event contains duplicate {label}")
