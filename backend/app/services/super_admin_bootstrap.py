from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.observability import AuditLog
from app.db.models.user import User, UserRole


class SuperAdminBootstrapDisabledError(RuntimeError):
    pass


class SuperAdminAlreadyExistsError(ValueError):
    pass


class SuperAdminInputError(ValueError):
    pass


@dataclass(frozen=True)
class SuperAdminBootstrapResult:
    user_id: str
    email: str
    username: str


def bootstrap_super_admin(
    db: Session,
    *,
    email: str,
    username: str,
    password: str,
    enabled: bool,
) -> SuperAdminBootstrapResult:
    if not enabled:
        raise SuperAdminBootstrapDisabledError("super admin bootstrap is disabled")

    normalized_email = _validated_email(email)
    normalized_username = username.strip()
    if not 3 <= len(normalized_username) <= 80:
        raise SuperAdminInputError("username must be between 3 and 80 characters")
    if len(password) < 16:
        raise SuperAdminInputError("super admin password must be at least 16 characters")

    existing = db.scalar(
        select(User).where(
            or_(
                User.email == normalized_email,
                User.username == normalized_username,
            )
        )
    )
    if existing is not None:
        raise SuperAdminAlreadyExistsError("email or username already exists")

    user = User(
        email=normalized_email,
        username=normalized_username,
        password_hash=hash_password(password),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            exchange_account_id=None,
            action="super_admin.bootstrap.created",
            severity="CRITICAL",
            payload={
                "created_user_id": user.id,
                "username": user.username,
                "source": "server_cli",
            },
        )
    )
    db.commit()
    return SuperAdminBootstrapResult(
        user_id=user.id,
        email=user.email,
        username=user.username,
    )


def _validated_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise SuperAdminInputError("invalid email address") from exc
