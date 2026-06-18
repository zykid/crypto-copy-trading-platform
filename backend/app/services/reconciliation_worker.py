from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trading import Position
from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationReport,
    reconcile_position_snapshots,
)
from app.services.reconciliation_hooks import (
    ReconciliationDriftAlertRuntime,
    ReconciliationHookPlan,
    ReconciliationNotificationChannel,
    build_reconciliation_hook_plan,
)
from app.services.reconciliation_persistence import (
    PersistedReconciliationHookPlan,
    persist_reconciliation_hook_plan,
)


class PositionSnapshotProvider(Protocol):
    def load_positions(
        self,
        *,
        user_id: str,
        exchange_account_id: str,
    ) -> tuple[PositionQuantitySnapshot, ...]: ...


@dataclass(frozen=True)
class ReconciliationSnapshotProviders:
    exchange: PositionSnapshotProvider
    database: PositionSnapshotProvider
    target: PositionSnapshotProvider


@dataclass(frozen=True)
class ReconciliationWorkerResult:
    report: PositionReconciliationReport
    hook_plan: ReconciliationHookPlan
    persisted: PersistedReconciliationHookPlan
    auto_fix_allowed: bool = False


class DatabasePositionSnapshotProvider:
    def __init__(self, db: Session) -> None:
        self._db = db

    def load_positions(
        self,
        *,
        user_id: str,
        exchange_account_id: str,
    ) -> tuple[PositionQuantitySnapshot, ...]:
        positions = self._db.scalars(
            select(Position)
            .where(
                Position.user_id == user_id,
                Position.exchange_account_id == exchange_account_id,
            )
            .order_by(Position.symbol)
        ).all()
        return tuple(
            PositionQuantitySnapshot(
                symbol=position.symbol,
                quantity=position.quantity,
            )
            for position in positions
        )


@dataclass(frozen=True)
class PositionReconciliationWorker:
    providers: ReconciliationSnapshotProviders
    quantity_tolerance: Decimal = Decimal("0")
    critical_threshold: Decimal = Decimal("1")
    notification_channels: tuple[ReconciliationNotificationChannel, ...] = (
        ReconciliationNotificationChannel.INTERNAL,
    )
    alert_runtime: ReconciliationDriftAlertRuntime | None = None

    def run_account(
        self,
        db: Session,
        *,
        user_id: str,
        exchange_account_id: str,
    ) -> ReconciliationWorkerResult:
        exchange_positions = self.providers.exchange.load_positions(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
        )
        database_positions = self.providers.database.load_positions(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
        )
        target_positions = self.providers.target.load_positions(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
        )
        report = reconcile_position_snapshots(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            exchange_positions=exchange_positions,
            database_positions=database_positions,
            target_positions=target_positions,
            quantity_tolerance=self.quantity_tolerance,
            critical_threshold=self.critical_threshold,
        )
        hook_plan = build_reconciliation_hook_plan(
            report,
            notification_channels=self.notification_channels,
            alert_runtime=self.alert_runtime,
        )
        persisted = persist_reconciliation_hook_plan(db, hook_plan)
        return ReconciliationWorkerResult(
            report=report,
            hook_plan=hook_plan,
            persisted=persisted,
            auto_fix_allowed=False,
        )
