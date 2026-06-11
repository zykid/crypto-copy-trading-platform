from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.observability import AuditLogResponse, SystemEventResponse
from app.services.observability_service import (
    AuditLogFilter,
    SystemEventFilter,
    observability_service,
)

router = APIRouter()


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    user_id: str | None = None,
    exchange_account_id: str | None = None,
    action: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return observability_service.list_audit_logs(
        db,
        AuditLogFilter(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            action=action,
            severity=severity,
            limit=limit,
        ),
    )


@router.get("/system-events", response_model=list[SystemEventResponse])
def list_system_events(
    user_id: str | None = None,
    exchange_account_id: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return observability_service.list_system_events(
        db,
        SystemEventFilter(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            event_type=event_type,
            severity=severity,
            limit=limit,
        ),
    )
