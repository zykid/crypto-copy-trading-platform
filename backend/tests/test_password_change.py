import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.models.observability import AuditLog
from app.services.users import (
    PasswordChangeError,
    change_password,
    create_user,
)


def test_password_change_updates_hash_and_writes_safe_audit(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="old-password-strong",
    )

    change_password(
        db_session,
        user=user,
        current_password="old-password-strong",
        new_password="new-password-strong",
    )

    assert user.auth_version == 1
    assert not verify_password("old-password-strong", user.password_hash)
    assert verify_password("new-password-strong", user.password_hash)

    record = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.password.changed")
    )
    assert record is not None
    assert record.user_id == user.id
    assert record.payload == {
        "user_id": user.id,
        "revoked_auth_version": 0,
        "new_auth_version": 1,
    }
    assert "old-password-strong" not in str(record.payload)
    assert "new-password-strong" not in str(record.payload)


def test_password_change_rejects_invalid_or_reused_password(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="old-password-strong",
    )
    original_hash = user.password_hash

    with pytest.raises(PasswordChangeError):
        change_password(
            db_session,
            user=user,
            current_password="wrong-password",
            new_password="new-password-strong",
        )
    with pytest.raises(PasswordChangeError):
        change_password(
            db_session,
            user=user,
            current_password="old-password-strong",
            new_password="old-password-strong",
        )

    assert user.password_hash == original_hash
    assert user.auth_version == 0
    assert db_session.scalar(select(AuditLog)) is None


def test_password_change_revokes_existing_access_token(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="old-password-strong",
    )
    old_token = create_access_token(user.id, auth_version=user.auth_version)
    assert get_current_user(token=old_token, db=db_session) == user

    change_password(
        db_session,
        user=user,
        current_password="old-password-strong",
        new_password="new-password-strong",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=old_token, db=db_session)
    assert exc_info.value.status_code == 401

    new_token = create_access_token(user.id, auth_version=user.auth_version)
    assert get_current_user(token=new_token, db=db_session) == user
