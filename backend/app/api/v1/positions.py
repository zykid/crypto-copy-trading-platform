from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import PositionDeltaPreview
from app.services.exchange_accounts import get_owned_account
from app.services.position_engine import calculate_delta, get_or_create_position

router = APIRouter()


@router.post("/{account_id}/target-preview", response_model=PositionDeltaPreview)
def preview_position_target(
    account_id: str,
    symbol: str,
    target_quantity: Decimal,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    position = get_or_create_position(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
        symbol=symbol.upper(),
    )
    delta = calculate_delta(
        symbol=position.symbol,
        current_quantity=position.quantity,
        target_quantity=target_quantity,
    )
    return PositionDeltaPreview(
        symbol=delta.symbol,
        current_quantity=delta.current_quantity,
        target_quantity=delta.target_quantity,
        delta_quantity=delta.delta_quantity,
        side=delta.side,
    )
