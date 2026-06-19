from sqlalchemy import func, select

from app.core.security import verify_password
from app.db.models.observability import AuditLog
from app.db.models.user import User, UserRole
from app.services.super_admin_bootstrap import (
    SuperAdminAlreadyExistsError,
    SuperAdminBootstrapDisabledError,
    bootstrap_super_admin,
)


def test_bootstrap_is_disabled_by_default(db_session) -> None:
    try:
        bootstrap_super_admin(
            db_session,
            email="root@example.com",
            username="root_admin",
            password="TemporaryPassword123!",
            enabled=False,
        )
    except SuperAdminBootstrapDisabledError:
        pass
    else:
        raise AssertionError("disabled bootstrap unexpectedly succeeded")

    assert db_session.scalar(select(func.count()).select_from(User)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_bootstrap_creates_super_admin_and_audit_atomically(db_session) -> None:
    password = "TemporaryPassword123!"
    result = bootstrap_super_admin(
        db_session,
        email="Root@Example.com",
        username="root_admin",
        password=password,
        enabled=True,
    )

    user = db_session.get(User, result.user_id)
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.user_id == result.user_id)
    )

    assert user is not None
    assert user.email == "Root@example.com"
    assert user.role == UserRole.SUPER_ADMIN
    assert verify_password(password, user.password_hash)
    assert password not in user.password_hash
    assert audit is not None
    assert audit.action == "super_admin.bootstrap.created"
    assert audit.severity == "CRITICAL"
    assert password not in str(audit.payload)


def test_bootstrap_refuses_existing_account_without_role_change(db_session) -> None:
    existing = User(
        email="existing@example.com",
        username="existing",
        password_hash="hash",
        role=UserRole.NORMAL_USER,
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    try:
        bootstrap_super_admin(
            db_session,
            email="existing@example.com",
            username="replacement",
            password="TemporaryPassword123!",
            enabled=True,
        )
    except SuperAdminAlreadyExistsError:
        pass
    else:
        raise AssertionError("existing account was unexpectedly promoted")

    db_session.refresh(existing)
    assert existing.role == UserRole.NORMAL_USER
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
