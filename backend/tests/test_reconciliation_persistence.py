from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    AuditLog,
    ExchangeAccount,
    ExchangeName,
    InternalNotification,
    NotificationPreference,
    SystemEvent,
    User,
)
from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationSeverity,
    reconcile_position_snapshots,
)
from app.services.reconciliation_hooks import (
    ReconciliationNotificationChannel,
    build_reconciliation_hook_plan,
)
from app.services.reconciliation_persistence import persist_reconciliation_hook_plan


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def create_user_and_account(db_session: Session) -> tuple[User, ExchangeAccount]:
    user = User(
        email="trader@example.com",
        username="trader",
        password_hash="hashed-password",
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


def build_drift_plan(user: User, account: ExchangeAccount):
    report = reconcile_position_snapshots(
        user_id=user.id,
        exchange_account_id=account.id,
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "0.7"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )
    return build_reconciliation_hook_plan(report)


def test_persist_reconciliation_hook_plan_writes_matched_audit_only(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    report = reconcile_position_snapshots(
        user_id=user.id,
        exchange_account_id=account.id,
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )
    plan = build_reconciliation_hook_plan(report)

    persisted = persist_reconciliation_hook_plan(db_session, plan)

    audit_logs = db_session.scalars(select(AuditLog)).all()
    system_events = db_session.scalars(select(SystemEvent)).all()
    notifications = db_session.scalars(select(InternalNotification)).all()
    assert len(audit_logs) == 1
    assert audit_logs[0] == persisted.audit_log
    assert audit_logs[0].action == "position_reconciliation.matched"
    assert audit_logs[0].payload["difference_count"] == 0
    assert persisted.system_event is None
    assert persisted.internal_notifications == ()
    assert system_events == []
    assert notifications == []


def test_persist_reconciliation_hook_plan_writes_drift_records(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    plan = build_drift_plan(user, account)

    persisted = persist_reconciliation_hook_plan(db_session, plan)

    audit_log = db_session.scalars(select(AuditLog)).one()
    system_event = db_session.scalars(select(SystemEvent)).one()
    notification = db_session.scalars(select(InternalNotification)).one()
    assert audit_log.action == "position_reconciliation.drift_detected"
    assert audit_log.severity == PositionReconciliationSeverity.WARNING.value
    assert system_event.event_type == "position_reconciliation.drift_detected"
    assert system_event.payload["status"] == "DRIFT_DETECTED"
    assert notification.channel == ReconciliationNotificationChannel.INTERNAL.value
    assert notification.is_read is False
    assert notification.payload["differences"][0]["exchange_database_delta"] == "0.3"
    assert persisted.system_event == system_event
    assert persisted.internal_notifications == (notification,)


def test_persist_reconciliation_hook_plan_does_not_store_external_notification_channels(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    report = reconcile_position_snapshots(
        user_id=user.id,
        exchange_account_id=account.id,
        exchange_positions=(snapshot("ETHUSDT", "3"),),
        database_positions=(snapshot("ETHUSDT", "0"),),
        target_positions=(snapshot("ETHUSDT", "0"),),
    )
    plan = build_reconciliation_hook_plan(
        report,
        notification_channels=(
            ReconciliationNotificationChannel.INTERNAL,
            ReconciliationNotificationChannel.EMAIL,
            ReconciliationNotificationChannel.WEBHOOK,
        ),
    )

    persisted = persist_reconciliation_hook_plan(db_session, plan)

    notifications = db_session.scalars(select(InternalNotification)).all()
    assert len(notifications) == 1
    assert notifications[0].channel == ReconciliationNotificationChannel.INTERNAL.value
    assert persisted.internal_notifications == (notifications[0],)


def test_persist_reconciliation_hook_plan_respects_position_drift_preference(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    db_session.add(
        NotificationPreference(
            user_id=user.id,
            position_drift_enabled=False,
        )
    )
    db_session.flush()
    plan = build_drift_plan(user, account)

    persisted = persist_reconciliation_hook_plan(db_session, plan)

    audit_log = db_session.scalars(select(AuditLog)).one()
    system_event = db_session.scalars(select(SystemEvent)).one()
    notifications = db_session.scalars(select(InternalNotification)).all()
    assert audit_log.action == "position_reconciliation.drift_detected"
    assert system_event.event_type == "position_reconciliation.drift_detected"
    assert persisted.internal_notifications == ()
    assert notifications == []
