from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.exchange_account import AccountMode
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.risk_setting import RiskSettingResponse, RiskSettingUpdate
from app.services.exchange_accounts import get_owned_account
from app.services.risk_engine import get_or_create_risk_settings, update_risk_settings

router = APIRouter()


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
    settings = get_or_create_risk_settings(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    return update_risk_settings(db, settings, payload.model_dump(exclude_unset=True))
