from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, create_reauthentication_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    ReauthenticationRequest,
    ReauthenticationResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.users import (
    DuplicateUserError,
    ReauthenticationError,
    authenticate_user,
    create_user,
    record_reauthentication,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return create_user(
            db,
            email=str(payload.email),
            username=payload.username,
            password=payload.password,
        )
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(
        db,
        username_or_email=payload.username_or_email,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username/email or password",
        )
    return TokenResponse(
        access_token=create_access_token(
            user.id,
            auth_version=user.auth_version,
        )
    )


@router.post("/reauthenticate", response_model=ReauthenticationResponse)
def reauthenticate(
    payload: ReauthenticationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReauthenticationResponse:
    try:
        record_reauthentication(
            db,
            user=current_user,
            password=payload.password,
        )
    except ReauthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="password reauthentication failed",
        ) from exc

    return ReauthenticationResponse(
        reauthentication_token=create_reauthentication_token(
            current_user.id,
            auth_version=current_user.auth_version,
        )
    )
