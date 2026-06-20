from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models.observability import AuditLog
from app.db.models.user import User, UserRole


class DuplicateUserError(ValueError):
    pass


class PasswordChangeError(ValueError):
    pass


def create_user(db: Session, *, email: str, username: str, password: str) -> User:
    existing = db.scalar(select(User).where(or_(User.email == email, User.username == username)))
    if existing is not None:
        raise DuplicateUserError("email or username already exists")
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        role=UserRole.NORMAL_USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username_or_email: str, password: str) -> User | None:
    user = db.scalar(
        select(User).where(
            or_(User.email == username_or_email, User.username == username_or_email)
        )
    )
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def change_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise PasswordChangeError("current password is invalid")
    if verify_password(new_password, user.password_hash):
        raise PasswordChangeError("new password must differ from current password")

    user.password_hash = hash_password(new_password)
    user.auth_version += 1
    db.add(
        AuditLog(
            user_id=user.id,
            exchange_account_id=None,
            action="user.password.changed",
            severity="WARNING",
            payload={
                "user_id": user.id,
                "revoked_auth_version": user.auth_version - 1,
                "new_auth_version": user.auth_version,
            },
        )
    )
    db.commit()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)
