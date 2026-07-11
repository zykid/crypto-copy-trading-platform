from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_admin_user,
    get_current_super_admin_user,
    get_reauthenticated_user,
)
from app.core.config import settings
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.system_control import (
    EmergencyStopActivateRequest,
    EmergencyStopDeactivateRequest,
    EmergencyStopResponse,
)
from app.services.emergency_stop import (
    EmergencyStopState,
    get_emergency_stop_state,
    set_emergency_stop,
)
from app.services.external_alerts import ExternalAlertConfig
from app.services.operational_alert_runtime import OperationalAlertRuntime

router = APIRouter()
_operational_alert_dispatch_state: dict[str, int] = {}


@router.get("/emergency-stop", response_model=EmergencyStopResponse)
def read_emergency_stop(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> EmergencyStopResponse:
    return _response(get_emergency_stop_state(db))


@router.post("/emergency-stop/activate", response_model=EmergencyStopResponse)
def activate_emergency_stop(
    payload: EmergencyStopActivateRequest,
    current_user: User = Depends(get_current_super_admin_user),
    db: Session = Depends(get_db),
) -> EmergencyStopResponse:
    state = set_emergency_stop(
        db,
        enabled=True,
        actor=current_user,
        reason=payload.reason,
    )
    _operational_alert_runtime().notify_emergency_stop_enabled(scope="global")
    return _response(state)


@router.post("/emergency-stop/deactivate", response_model=EmergencyStopResponse)
def deactivate_emergency_stop(
    payload: EmergencyStopDeactivateRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> EmergencyStopResponse:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super admin privileges required",
        )
    return _response(
        set_emergency_stop(
            db,
            enabled=False,
            actor=current_user,
            reason=payload.reason,
        )
    )


def _response(state: EmergencyStopState) -> EmergencyStopResponse:
    return EmergencyStopResponse(
        enabled=state.enabled,
        reason=state.reason,
        changed_by_user_id=state.changed_by_user_id,
        changed_at=state.changed_at,
    )


def _operational_alert_runtime() -> OperationalAlertRuntime:
    return OperationalAlertRuntime(
        ExternalAlertConfig(
            telegram_enabled=settings.telegram_alerts_enabled,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
            email_enabled=settings.email_alerts_enabled,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            alert_email_from=settings.alert_email_from,
            alert_email_to=settings.alert_email_to,
            webhook_enabled=settings.webhook_alerts_enabled,
            webhook_url=settings.alert_webhook_url,
            webhook_secret=settings.alert_webhook_secret,
            timeout_seconds=settings.alert_timeout_seconds,
        ),
        dispatch_state=_operational_alert_dispatch_state,
    )
