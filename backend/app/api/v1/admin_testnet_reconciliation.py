from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_reauthenticated_user
from app.core.config import settings
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.exchange_account import (
    TestnetOrderReconciliationItemResponse,
    TestnetOrderReconciliationResponse,
)
from app.services.testnet_order_reconciliation import (
    TestnetOrderReconciliationBlockedError,
    reconcile_pending_testnet_orders,
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
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super admin privileges required",
        )
    if not settings.testnet_adapters_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TESTNET_ADAPTERS_ENABLED must be true before reconciliation",
        )
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
