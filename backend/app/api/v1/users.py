from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    UserResponse,
)
from app.services.users import PasswordChangeError, change_password

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/password", response_model=PasswordChangeResponse)
def update_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PasswordChangeResponse:
    try:
        change_password(
            db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except PasswordChangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password change rejected",
        ) from exc
    return PasswordChangeResponse(changed=True)
