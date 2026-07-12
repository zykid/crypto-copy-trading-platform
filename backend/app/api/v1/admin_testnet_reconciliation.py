Exit code: 0
Wall time: 1.7 seconds
Output:
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_reauthenticated_user
from app.core.config import settings
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.exchange_account import (
    TestnetOrderReconciliationItemResponse,
    TestnetOrderReconciliationResponse,
    TestnetUserStreamConsumeRequest,
    TestnetUserStreamConsumeResponse,
)
from app.services.testnet_order_reconciliation import (
    TestnetOrderReconciliationBlockedError,
    reconcile_pending_testnet_orders,
)
from app.services.testnet_user_stream_service import (
    TestnetUserStreamBlockedError,
    consume_bounded_testnet_user_stream,
)

router = APIRouter()


@router.post(
    "/accounts/{account_id}/order-reconciliation",
    response_model=TestnetOrderReconciliationResponse,
)
def reconcile_testnet_order_statuses(
    account_id: str,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> TestnetOrderReconciliationResponse:
    _require_super_admin(current_user)
    _require_testnet_enabled()
    try:
        result = reconcile_pending_testnet_orders(
            db,
            user_id=current_user.id,
            exchange_account_id=account_id,
        )
    except TestnetOrderReconciliationBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="testnet order reconciliation is blocked",
        ) from exc
    return TestnetOrderReconciliationResponse(
        exchange_account_id=result.exchange_account_id,
        attempted=result.attempted,
        transitioned=result.transitioned,
        failed=result.failed,
        items=[
            TestnetOrderReconciliationItemResponse(
                execution_id=item.execution_id,
                status=item.status,
                transitioned=(
                    item.lifecycle_result.transitioned
                    if item.lifecycle_result is not None
                    else False
                ),
                failure_type=item.failure_type,
            )
            for item in result.items
        ],
    )


@router.post(
    "/accounts/{account_id}/user-stream-consume",
    response_model=TestnetUserStreamConsumeResponse,
)
def consume_testnet_user_stream(
    account_id: str,
    payload: TestnetUserStreamConsumeRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> TestnetUserStreamConsumeResponse:
    _require_super_admin(current_user)
    _require_testnet_enabled()
    if payload.acknowledgement != "CONSUME_TESTNET_USER_STREAM_READ_ONLY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="explicit user stream acknowledgement is required",
        )
    try:
        result = consume_bounded_testnet_user_stream(
            db,
            user_id=current_user.id,
            exchange_account_id=account_id,
            testnet_adapters_enabled=settings.testnet_adapters_enabled,
            max_messages=payload.max_messages,
        )
    except TestnetUserStreamBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="testnet user stream consumption is blocked",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="testnet user stream transport failed",
        ) from exc
    return TestnetUserStreamConsumeResponse(**result.__dict__)


def _require_super_admin(current_user: User) -> None:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super admin privileges required",
        )


def _require_testnet_enabled() -> None:
    if not settings.testnet_adapters_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TESTNET_ADAPTERS_ENABLED must be true before this operation",
        )

