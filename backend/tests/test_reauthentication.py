from inspect import signature

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_reauthenticated_user
from app.api.v1.exchange_accounts import remove_api_key, set_api_key
from app.core.security import (
    create_access_token,
    create_reauthentication_token,
)
from app.db.models.observability import AuditLog
from app.services.users import (
    ReauthenticationError,
    create_user,
    record_reauthentication,
)


def test_reauthentication_records_success_without_sensitive_data(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )

    record_reauthentication(
        db_session,
        user=user,
        password="very-strong-password",
    )

    record = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "user.reauthentication.succeeded"
        )
    )
    assert record is not None
    assert record.payload == {"user_id": user.id}
    assert "very-strong-password" not in str(record.payload)


def test_failed_reauthentication_is_audited(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )

    with pytest.raises(ReauthenticationError):
        record_reauthentication(
            db_session,
            user=user,
            password="wrong-password",
        )

    record = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "user.reauthentication.failed"
        )
    )
    assert record is not None
    assert record.payload == {
        "user_id": user.id,
        "reason": "invalid_password",
    }
    assert "wrong-password" not in str(record.payload)


def test_reauthentication_token_is_scoped_and_not_an_access_token(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    token = create_reauthentication_token(
        user.id,
        auth_version=user.auth_version,
    )

    assert (
        get_reauthenticated_user(
            x_reauth_token=token,
            current_user=user,
        )
        == user
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401


def test_reauthentication_token_must_match_user_and_auth_version(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    other_user = create_user(
        db_session,
        email="bob@example.com",
        username="bob",
        password="very-strong-password",
    )
    token = create_reauthentication_token(
        user.id,
        auth_version=user.auth_version,
    )

    with pytest.raises(HTTPException):
        get_reauthenticated_user(
            x_reauth_token=token,
            current_user=other_user,
        )

    user.auth_version += 1
    with pytest.raises(HTTPException):
        get_reauthenticated_user(
            x_reauth_token=token,
            current_user=user,
        )

    access_token = create_access_token(
        user.id,
        auth_version=user.auth_version,
    )
    with pytest.raises(HTTPException):
        get_reauthenticated_user(
            x_reauth_token=access_token,
            current_user=user,
        )


def test_set_api_key_requires_recent_reauthentication() -> None:
    dependency = signature(set_api_key).parameters["current_user"].default
    assert dependency.dependency is get_reauthenticated_user


def test_remove_api_key_requires_authenticated_session() -> None:
    dependency = signature(remove_api_key).parameters["current_user"].default
    assert dependency.dependency is get_current_user
