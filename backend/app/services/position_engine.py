from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trading import OrderSide, Position


@dataclass(frozen=True)
class PositionDelta:
    symbol: str
    current_quantity: Decimal
    target_quantity: Decimal
    delta_quantity: Decimal
    side: OrderSide | None


def get_or_create_position(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    symbol: str,
) -> Position:
    position = db.scalar(
        select(Position).where(
            Position.user_id == user_id,
            Position.exchange_account_id == exchange_account_id,
            Position.symbol == symbol,
        )
    )
    if position is None:
        position = Position(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            symbol=symbol,
            quantity=Decimal("0"),
        )
        db.add(position)
        db.commit()
        db.refresh(position)
    return position


def calculate_delta(
    *,
    symbol: str,
    current_quantity: Decimal,
    target_quantity: Decimal,
) -> PositionDelta:
    delta = target_quantity - current_quantity
    side = None
    if delta > 0:
        side = OrderSide.BUY
    elif delta < 0:
        side = OrderSide.SELL
    return PositionDelta(
        symbol=symbol,
        current_quantity=current_quantity,
        target_quantity=target_quantity,
        delta_quantity=abs(delta),
        side=side,
    )


def apply_fill(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    symbol: str,
    side: OrderSide,
    quantity: Decimal,
) -> Position:
    position = get_or_create_position(
        db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
        symbol=symbol,
    )
    if side == OrderSide.BUY:
        position.quantity += quantity
    else:
        position.quantity -= quantity
    db.commit()
    db.refresh(position)
    return position
