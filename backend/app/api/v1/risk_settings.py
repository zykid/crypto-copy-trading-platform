from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.exchange_account import AccountMode
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.risk_setting import RiskSettingResponse, RiskSettingUpdate
from app.services.exchange_accounts import get_owned_account
from app.services.external_alerts import ExternalAlertConfig
from app.services.operational_alert_runtime import OperationalAlertRuntime
from app.services.risk_engine import get_or_create_risk_settings, update_risk_settings

router = APIRouter()
_operational_alert_dispatch_state: dict[str, int] = {}


@router.get("/{account_id}", response_model=RiskSettingResponse)
def read_risk_settings(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return get_or_create_risk_settings(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )


@router.patch("/{account_id}", response_model=RiskSettingResponse)
def patch_risk_settings(
    account_id: str,
    payload: RiskSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if account.account_mode != AccountMode.SIMULATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="risk settings can only be modified for SIMULATION accounts in V1",
        )
    settings_obj = get_or_create_risk_settings(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    return update_risk_settings(
        db,
        settings_obj,
        payload.model_dump(exclude_unset=True),
        alert_runtime=_operational_alert_runtime(),
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
