from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import ManualSignalCreate, TradingSignalResponse
from app.services.signal_engine import create_manual_signal

router = APIRouter()


@router.post("/manual", response_model=TradingSignalResponse, status_code=status.HTTP_201_CREATED)
def create_manual_trading_signal(
    payload: ManualSignalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_manual_signal(
            db,
            user_id=current_user.id,
            symbol=payload.symbol,
            side=payload.side,
            order_type=payload.order_type,
            price=payload.price,
            quantity=payload.quantity,
            target_position_quantity=payload.target_position_quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
