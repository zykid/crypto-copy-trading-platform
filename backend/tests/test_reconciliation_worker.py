from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    AuditLog,
    ExchangeAccount,
    ExchangeName,
    InternalNotification,
    SystemEvent,
    User,
)
from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationStatus,
)
from app.services.reconciliation_hooks import ReconciliationNotificationChannel
from app.services.reconciliation_worker import (
    PositionReconciliationWorker,
    ReconciliationSnapshotProviders,
)


@dataclass
class FakePositionProvider:
    positions: tuple[PositionQuantitySnapshot, ...]
    calls: list[tuple[str, str]] = field(default_factory=list)

    def load_positions(
        self,
        *,
        user_id: str,
        exchange_account_id: str,
    ) -> tuple[PositionQuantitySnapshot, ...]:
        self.calls.append((user_id, exchange_account_id))
        return self.positions


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def create_user_and_account(db_session: Session) -> tuple[User, ExchangeAccount]:
    user = User(
        email="worker@example.com",
        username="worker",
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


def test_reconciliation_worker_persists_matched_audit_log(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    exchange = FakePositionProvider((snapshot("BTCUSDT", "1"),))
    database = FakePositionProvider((snapshot("BTCUSDT", "1"),))
    target = FakePositionProvider((snapshot("BTCUSDT", "1"),))
    worker = PositionReconciliationWorker(
        providers=ReconciliationSnapshotProviders(
            exchange=exchange,
            database=database,
            target=target,
        ),
    )

    result = worker.run_account(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )

    audit_logs = db_session.scalars(select(AuditLog)).all()
    assert result.report.status == PositionReconciliationStatus.MATCHED
    assert result.report.auto_fix_allowed is False
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "position_reconciliation.matched"
    assert result.persisted.audit_log == audit_logs[0]
    assert db_session.scalars(select(SystemEvent)).all() == []
    assert db_session.scalars(select(InternalNotification)).all() == []
    assert exchange.calls == [(user.id, account.id)]
    assert database.calls == [(user.id, account.id)]
    assert target.calls == [(user.id, account.id)]


def test_reconciliation_worker_persists_drift_observability_records(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    worker = PositionReconciliationWorker(
        providers=ReconciliationSnapshotProviders(
            exchange=FakePositionProvider((snapshot("ETHUSDT", "3"),)),
            database=FakePositionProvider((snapshot("ETHUSDT", "0"),)),
            target=FakePositionProvider((snapshot("ETHUSDT", "0"),)),
        ),
        notification_channels=(
            ReconciliationNotificationChannel.INTERNAL,
            ReconciliationNotificationChannel.EMAIL,
            ReconciliationNotificationChannel.WEBHOOK,
        ),
    )

    result = worker.run_account(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )

    audit_log = db_session.scalars(select(AuditLog)).one()
    system_event = db_session.scalars(select(SystemEvent)).one()
    notifications = db_session.scalars(select(InternalNotification)).all()
    assert result.report.status == PositionReconciliationStatus.DRIFT_DETECTED
    assert result.report.auto_fix_allowed is False
    assert result.hook_plan.auto_fix_allowed is False
    assert audit_log.action == "position_reconciliation.drift_detected"
    assert system_event.event_type == "position_reconciliation.drift_detected"
    assert len(notifications) == 1
    assert notifications[0].channel == ReconciliationNotificationChannel.INTERNAL.value
    assert notifications[0].payload["auto_fix_allowed"] is False
    assert result.persisted.system_event == system_event
    assert result.persisted.internal_notifications == (notifications[0],)
