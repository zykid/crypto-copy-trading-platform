from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models.user import User, UserRole


class DuplicateUserError(ValueError):
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


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)
