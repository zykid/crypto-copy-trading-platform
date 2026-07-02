from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.models import (
    AccountMode,
    AuditLog,
    ExchangeAccount,
    ExchangeName,
    SystemEvent,
    User,
    UserRole,
)
from app.services.observability_service import (
    AuditLogFilter,
    ObservabilityService,
    SystemEventFilter,
)


def create_user_and_account(
    db_session: Session,
    *,
    email: str = "audit@example.com",
    username: str = "audit-user",
    role: UserRole = UserRole.NORMAL_USER,
) -> tuple[User, ExchangeAccount]:
    user = User(
        email=email,
        username=username,
        password_hash="hashed-password",
        role=role,
    )
    db_session.add(user)
    db_session.flush()
    account = ExchangeAccount(
        user_id=user.id,
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.TESTNET,
        account_label="testnet mock",
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def create_audit_log(
    db_session: Session,
    *,
    user: User,
    account: ExchangeAccount,
    action: str,
    severity: str,
    created_at: datetime | None = None,
) -> AuditLog:
    values: dict[str, datetime] = {}
    if created_at is not None:
        values["created_at"] = created_at
    record = AuditLog(
        user_id=user.id,
        exchange_account_id=account.id,
        action=action,
        severity=severity,
        payload={"action": action},
        **values,
    )
    db_session.add(record)
    db_session.flush()
    return record


def create_system_event(
    db_session: Session,
    *,
    user: User,
    account: ExchangeAccount,
    event_type: str,
    severity: str,
    created_at: datetime | None = None,
) -> SystemEvent:
    values: dict[str, datetime] = {}
    if created_at is not None:
        values["created_at"] = created_at
    record = SystemEvent(
        user_id=user.id,
        exchange_account_id=account.id,
        event_type=event_type,
        severity=severity,
        payload={"event_type": event_type},
        **values,
    )
    db_session.add(record)
    db_session.flush()
    return record


def test_list_audit_logs_filters_by_user_action_and_severity(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    other_user, other_account = create_user_and_account(
        db_session,
        email="other-audit@example.com",
        username="other-audit-user",
    )
    service = ObservabilityService()
    expected = create_audit_log(
        db_session,
        user=user,
        account=account,
        action="position_reconciliation.drift_detected",
        severity="WARNING",
    )
    create_audit_log(
        db_session,
        user=other_user,
        account=other_account,
        action="position_reconciliation.drift_detected",
        severity="WARNING",
    )
    create_audit_log(
        db_session,
        user=user,
        account=account,
        action="position_reconciliation.matched",
        severity="INFO",
    )

    records = service.list_audit_logs(
        db_session,
        AuditLogFilter(
            user_id=user.id,
            action="position_reconciliation.drift_detected",
            severity="WARNING",
        ),
    )

    assert records == (expected,)


def test_list_system_events_filters_by_event_type(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = ObservabilityService()
    expected = create_system_event(
        db_session,
        user=user,
        account=account,
        event_type="position_reconciliation.drift_detected",
        severity="WARNING",
    )
    create_system_event(
        db_session,
        user=user,
        account=account,
        event_type="rate_limit.exceeded",
        severity="WARNING",
    )

    records = service.list_system_events(
        db_session,
        SystemEventFilter(event_type="position_reconciliation.drift_detected"),
    )

    assert records == (expected,)


def test_list_audit_logs_filters_by_created_range(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = ObservabilityService()
    create_audit_log(
        db_session,
        user=user,
        account=account,
        action="audit.before",
        severity="INFO",
        created_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
    )
    expected = create_audit_log(
        db_session,
        user=user,
        account=account,
        action="audit.in_range",
        severity="WARNING",
        created_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
    )
    create_audit_log(
        db_session,
        user=user,
        account=account,
        action="audit.after",
        severity="ERROR",
        created_at=datetime(2026, 6, 3, 0, 0, tzinfo=UTC),
    )

    records = service.list_audit_logs(
        db_session,
        AuditLogFilter(
            created_from=datetime(2026, 6, 2, 0, 0, tzinfo=UTC),
            created_to=datetime(2026, 6, 2, 23, 59, tzinfo=UTC),
        ),
    )

    assert records == (expected,)


def test_list_system_events_filters_by_created_range(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = ObservabilityService()
    create_system_event(
        db_session,
        user=user,
        account=account,
        event_type="system.before",
        severity="INFO",
        created_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
    )
    expected = create_system_event(
        db_session,
        user=user,
        account=account,
        event_type="system.in_range",
        severity="WARNING",
        created_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
    )
    create_system_event(
        db_session,
        user=user,
        account=account,
        event_type="system.after",
        severity="ERROR",
        created_at=datetime(2026, 6, 3, 0, 0, tzinfo=UTC),
    )

    records = service.list_system_events(
        db_session,
        SystemEventFilter(
            created_from=datetime(2026, 6, 2, 0, 0, tzinfo=UTC),
            created_to=datetime(2026, 6, 2, 23, 59, tzinfo=UTC),
        ),
    )

    assert records == (expected,)


def test_observability_limit_is_bounded(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = ObservabilityService()
    for index in range(105):
        create_audit_log(
            db_session,
            user=user,
            account=account,
            action=f"audit.{index}",
            severity="INFO",
        )

    records = service.list_audit_logs(db_session, AuditLogFilter(limit=500))

    assert len(records) == 100


def test_get_current_admin_user_allows_admin_user(db_session: Session) -> None:
    admin_user, _account = create_user_and_account(
        db_session,
        email="admin@example.com",
        username="admin-user",
        role=UserRole.ADMIN,
    )

    assert get_current_admin_user(admin_user) == admin_user


def test_get_current_admin_user_rejects_normal_user(db_session: Session) -> None:
    normal_user, _account = create_user_and_account(db_session)

    with pytest.raises(HTTPException) as exc_info:
        get_current_admin_user(normal_user)

    assert exc_info.value.status_code == 403
