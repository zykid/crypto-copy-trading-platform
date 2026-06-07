from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import UserPermission


def list_permissions_for_owner(db: Session, *, owner_user_id: str) -> list[UserPermission]:
    statement = select(UserPermission).where(UserPermission.owner_user_id == owner_user_id)
    return list(db.scalars(statement))


def create_permission(
    db: Session,
    *,
    owner_user_id: str,
    data: dict[str, object],
) -> UserPermission:
    permission = UserPermission(owner_user_id=owner_user_id, **data)
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def get_owned_permission(
    db: Session,
    *,
    owner_user_id: str,
    permission_id: str,
) -> UserPermission | None:
    return db.scalar(
        select(UserPermission).where(
            UserPermission.id == permission_id,
            UserPermission.owner_user_id == owner_user_id,
        )
    )


def update_permission(
    permission: UserPermission,
    data: dict[str, object],
    db: Session,
) -> UserPermission:
    for key, value in data.items():
        if value is not None:
            setattr(permission, key, value)
    db.commit()
    db.refresh(permission)
    return permission


def delete_permission(permission: UserPermission, db: Session) -> None:
    db.delete(permission)
    db.commit()
