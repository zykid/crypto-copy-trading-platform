from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.trading import OrderSide, OrderType, SignalSource, TradingSignal


def create_manual_signal(
    db: Session,
    *,
    user_id: str,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    price: Decimal | None,
    quantity: Decimal | None,
    target_position_quantity: Decimal | None,
) -> TradingSignal:
    signal = TradingSignal(
        user_id=user_id,
        source=SignalSource.MANUAL,
        symbol=symbol.upper(),
        side=side,
        order_type=order_type,
        price=price,
        quantity=quantity,
        target_position_quantity=target_position_quantity,
        raw_payload={"source": SignalSource.MANUAL.value},
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal
