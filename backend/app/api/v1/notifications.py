from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.notification import InternalNotificationResponse
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/", response_model=list[InternalNotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.list_internal_notifications(
        db,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
    )


@router.post("/{notification_id}/read", response_model=InternalNotificationResponse)
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = notification_service.mark_internal_notification_read(
        db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="notification not found",
        )
    return notification
