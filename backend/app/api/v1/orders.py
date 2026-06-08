from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import (
    ExecuteSignalRequest,
    OrderExecutionResponse,
    TestnetOrderNotReadyResponse,
    TestnetOrderSubmitRequest,
)
from app.services.order_engine import execute_signal_for_account
from app.services.testnet_order_api import (
    TestnetOrderApiBlockedError,
    build_testnet_order_api_context,
)

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


@router.post("/testnet/submit", response_model=TestnetOrderNotReadyResponse)
def submit_testnet_order(
    payload: TestnetOrderSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        context = build_testnet_order_api_context(
            db,
            user_id=current_user.id,
            payload=payload,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TestnetOrderApiBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc

    response = TestnetOrderNotReadyResponse(
        exchange_account_id=context.account.id,
        client_order_id=context.order.client_order_id,
        detail=(
            "testnet order API preflight passed, but credential decryption and real testnet "
            "transport are not enabled yet"
        ),
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=response.model_dump(),
    )
