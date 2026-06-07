from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import ExecuteSignalRequest, OrderExecutionResponse
from app.services.order_engine import execute_signal_for_account

router = APIRouter()


@router.post("/execute-signal/{signal_id}", response_model=OrderExecutionResponse)
def execute_signal(
    signal_id: str,
    payload: ExecuteSignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return execute_signal_for_account(
            db,
            user_id=current_user.id,
            signal_id=signal_id,
            exchange_account_id=payload.exchange_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
