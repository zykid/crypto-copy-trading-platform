import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.api.v1.admin_observability import list_audit_logs
from app.db.models import AccountMode, AuditLog, ExchangeAccount, ExchangeName, User, UserRole


def _create_user(
    db_session: Session,
    *,
    email: str,
    username: str,
    role: UserRole,
) -> User:
    user = User(
        email=email,
        username=username,
        password_hash="hashed-password",
        role=role,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_admin_observability_audit_logs_requires_admin(db_session: Session) -> None:
    normal_user = _create_user(
        db_session,
        email="normal-audit-api@example.com",
        username="normal-audit-api",
        role=UserRole.NORMAL_USER,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_admin_user(normal_user)

    assert exc_info.value.status_code == 403


def test_admin_observability_filters_audit_logs(db_session: Session) -> None:
    admin_user = _create_user(
        db_session,
        email="admin-audit-api@example.com",
        username="admin-audit-api",
        role=UserRole.ADMIN,
    )
    other_user = _create_user(
        db_session,
        email="other-audit-api@example.com",
        username="other-audit-api",
        role=UserRole.NORMAL_USER,
    )
    account = ExchangeAccount(
        user_id=admin_user.id,
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.SIMULATION,
        account_label="mock audit",
    )
    db_session.add(account)
    db_session.flush()
    expected = AuditLog(
        user_id=admin_user.id,
        exchange_account_id=account.id,
        action="real.small_fund.review_recorded",
        severity="INFO",
        payload={"order_submission_authorized": False},
    )
    db_session.add(expected)
    db_session.add(
        AuditLog(
            user_id=other_user.id,
            exchange_account_id=None,
            action="real.small_fund.review_recorded",
            severity="INFO",
            payload={"order_submission_authorized": False},
        )
    )
    db_session.add(
        AuditLog(
            user_id=admin_user.id,
            exchange_account_id=account.id,
            action="real.small_fund.review_recorded",
            severity="ERROR",
            payload={"order_submission_authorized": False},
        )
    )
    db_session.flush()

    records = list_audit_logs(
        user_id=admin_user.id,
        exchange_account_id=account.id,
        action="real.small_fund.review_recorded",
        severity="INFO",
        limit=50,
        _admin_user=admin_user,
        db=db_session,
    )

    assert len(records) == 1
    assert records[0].id == expected.id
    assert records[0].payload["order_submission_authorized"] is False
