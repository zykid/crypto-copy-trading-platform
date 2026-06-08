from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import (
    ExecuteSignalRequest,
    OrderExecutionResponse,
    TestnetOrderSubmitRequest,
    TestnetOrderSubmitResponse,
)
from app.services.order_engine import execute_signal_for_account
from app.services.rate_limit_service import RateLimitExceededError, runtime_rate_limit_service
from app.services.testnet_http_client import create_testnet_signed_http_client
from app.services.testnet_order_api import (
    TestnetOrderApiBlockedError,
    build_testnet_order_api_context,
)
from app.services.testnet_order_execution import execute_testnet_order

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


@router.post("/testnet/submit", response_model=TestnetOrderSubmitResponse)
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
        http_client = create_testnet_signed_http_client(
            exchange_name=context.account.exchange_name,
        )
        result = execute_testnet_order(
            order=context.order,
            gate_result=context.gate_result,
            http_client=http_client,
            credentials=context.credentials,
            rate_limiter=runtime_rate_limit_service,
            exchange_account_id=context.account.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TestnetOrderApiBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reasons": list(exc.reasons)},
        ) from exc
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="testnet order rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="testnet exchange request failed",
        ) from exc

    return TestnetOrderSubmitResponse(
        exchange_account_id=context.account.id,
        exchange_name=result.exchange_name,
        client_order_id=result.client_order_id,
        request_method=result.request_method,
        request_path=result.request_path,
        exchange_response=result.exchange_response,
    )
