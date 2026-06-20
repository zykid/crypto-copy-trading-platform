import uuid
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    NORMAL_USER = "normal_user"
    TEAM_ADMIN = "team_admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    mfa_pending_secret_encrypted: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    mfa_last_used_step: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    mfa_recovery_code_hashes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.NORMAL_USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (UniqueConstraint("owner_user_id", "grantee_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    grantee_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    view_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    copy_follow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pause_follow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edit_copy_rule: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trade_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
