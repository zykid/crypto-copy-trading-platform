from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_reauthenticated_user
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.user import (
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaDisableResponse,
    MfaEnrollmentResponse,
    MfaStatusResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    UserResponse,
)
from app.services.mfa import (
    MfaEnrollmentError,
    MfaVerificationError,
    confirm_mfa_enrollment,
    disable_mfa,
    get_mfa_status,
    start_mfa_enrollment,
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



def _require_super_admin(user: User) -> None:
    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super admin privileges required",
        )


@router.get("/me/mfa", response_model=MfaStatusResponse)
def read_mfa_status(
    current_user: User = Depends(get_current_user),
) -> MfaStatusResponse:
    enabled, enrollment_pending = get_mfa_status(current_user)
    return MfaStatusResponse(
        enabled=enabled,
        enrollment_pending=enrollment_pending,
    )


@router.post("/me/mfa/enroll", response_model=MfaEnrollmentResponse)
def enroll_mfa(
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> MfaEnrollmentResponse:
    _require_super_admin(current_user)
    try:
        secret, provisioning_uri = start_mfa_enrollment(
            db,
            user=current_user,
        )
    except MfaEnrollmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="mfa enrollment rejected",
        ) from exc
    return MfaEnrollmentResponse(
        provisioning_uri=provisioning_uri,
        manual_entry_key=secret,
    )


@router.post("/me/mfa/confirm", response_model=MfaConfirmResponse)
def confirm_mfa(
    payload: MfaConfirmRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> MfaConfirmResponse:
    _require_super_admin(current_user)
    try:
        recovery_codes = confirm_mfa_enrollment(
            db,
            user=current_user,
            code=payload.code,
        )
    except (MfaEnrollmentError, MfaVerificationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mfa confirmation rejected",
        ) from exc
    return MfaConfirmResponse(
        enabled=True,
        recovery_codes=recovery_codes,
    )


@router.post("/me/mfa/disable", response_model=MfaDisableResponse)
def remove_mfa(
    payload: MfaDisableRequest,
    current_user: User = Depends(get_reauthenticated_user),
    db: Session = Depends(get_db),
) -> MfaDisableResponse:
    _require_super_admin(current_user)
    try:
        disable_mfa(
            db,
            user=current_user,
            code=payload.code,
        )
    except (MfaEnrollmentError, MfaVerificationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mfa disable rejected",
        ) from exc
    return MfaDisableResponse(disabled=True)
