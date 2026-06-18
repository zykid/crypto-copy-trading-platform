from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    AuditLog,
    ExchangeAccount,
    ExchangeName,
    InternalNotification,
    Position,
    SystemEvent,
    User,
)
from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationStatus,
)
from app.services.reconciliation_hooks import ReconciliationNotificationChannel
from app.services.reconciliation_worker import (
    DatabasePositionSnapshotProvider,
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


class FailingPositionProvider:
    def load_positions(
        self,
        *,
        user_id: str,
        exchange_account_id: str,
    ) -> tuple[PositionQuantitySnapshot, ...]:
        raise RuntimeError("snapshot provider unavailable")


class CapturingReconciliationAlertRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify_reconciliation_drift(
        self,
        *,
        status: str,
        severity: str,
        difference_count: int,
    ) -> tuple[object, ...]:
        self.calls.append(
            {
                "status": status,
                "severity": severity,
                "difference_count": difference_count,
            }
        )
        return ()


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def create_user_and_account(
    db_session: Session,
    *,
    suffix: str = "worker",
) -> tuple[User, ExchangeAccount]:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        password_hash="hashed-password",
    )
    db_session.add(user)
    db_session.flush()
    account = ExchangeAccount(
        user_id=user.id,
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.TESTNET,
        account_label=f"{suffix} testnet mock",
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def test_database_position_snapshot_provider_is_scoped_by_user_and_account(
    db_session: Session,
) -> None:
    owner, owner_account = create_user_and_account(db_session, suffix="owner")
    other, other_account = create_user_and_account(db_session, suffix="other")
    db_session.add_all(
        (
            Position(
                user_id=owner.id,
                exchange_account_id=owner_account.id,
                symbol="BTCUSDT",
                quantity=Decimal("1"),
            ),
            Position(
                user_id=other.id,
                exchange_account_id=other_account.id,
                symbol="ETHUSDT",
                quantity=Decimal("5"),
            ),
        )
    )
    db_session.flush()
    provider = DatabasePositionSnapshotProvider(db_session)

    positions = provider.load_positions(
        user_id=owner.id,
        exchange_account_id=owner_account.id,
    )

    assert positions == (snapshot("BTCUSDT", "1"),)


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
    assert result.auto_fix_allowed is False
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
    alert_runtime = CapturingReconciliationAlertRuntime()
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
        alert_runtime=alert_runtime,
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
    assert result.auto_fix_allowed is False
    assert audit_log.action == "position_reconciliation.drift_detected"
    assert system_event.event_type == "position_reconciliation.drift_detected"
    assert len(notifications) == 1
    assert notifications[0].channel == ReconciliationNotificationChannel.INTERNAL.value
    assert notifications[0].payload["auto_fix_allowed"] is False
    assert result.persisted.system_event == system_event
    assert result.persisted.internal_notifications == (notifications[0],)
    assert alert_runtime.calls == [
        {
            "status": "DRIFT_DETECTED",
            "severity": "CRITICAL",
            "difference_count": 1,
        }
    ]


def test_reconciliation_worker_does_not_persist_when_snapshot_provider_fails(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    target = FakePositionProvider((snapshot("BTCUSDT", "1"),))
    worker = PositionReconciliationWorker(
        providers=ReconciliationSnapshotProviders(
            exchange=FakePositionProvider((snapshot("BTCUSDT", "1"),)),
            database=FailingPositionProvider(),
            target=target,
        ),
    )

    with pytest.raises(RuntimeError, match="snapshot provider unavailable"):
        worker.run_account(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
        )

    assert db_session.scalars(select(AuditLog)).all() == []
    assert db_session.scalars(select(SystemEvent)).all() == []
    assert db_session.scalars(select(InternalNotification)).all() == []
    assert target.calls == []
