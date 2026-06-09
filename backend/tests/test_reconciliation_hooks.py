from decimal import Decimal

from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationSeverity,
    PositionReconciliationStatus,
    reconcile_position_snapshots,
)
from app.services.reconciliation_hooks import (
    ReconciliationNotificationChannel,
    build_reconciliation_hook_plan,
)


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def test_build_reconciliation_hook_plan_records_matched_audit_without_notifications() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    plan = build_reconciliation_hook_plan(report)

    assert plan.audit_entry.action == "position_reconciliation.matched"
    assert plan.audit_entry.severity == PositionReconciliationSeverity.OK
    assert plan.audit_entry.payload["status"] == PositionReconciliationStatus.MATCHED.value
    assert plan.audit_entry.payload["difference_count"] == 0
    assert plan.system_event is None
    assert plan.notifications == ()
    assert plan.auto_fix_allowed is False


def test_build_reconciliation_hook_plan_records_drift_event_and_notification() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "0.7"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    plan = build_reconciliation_hook_plan(report)

    assert plan.audit_entry.action == "position_reconciliation.drift_detected"
    assert plan.audit_entry.severity == PositionReconciliationSeverity.WARNING
    assert plan.system_event is not None
    assert plan.system_event.event_type == "position_reconciliation.drift_detected"
    assert plan.system_event.severity == PositionReconciliationSeverity.WARNING
    assert len(plan.notifications) == 1
    notification = plan.notifications[0]
    assert notification.channel == ReconciliationNotificationChannel.INTERNAL
    assert notification.severity == PositionReconciliationSeverity.WARNING
    assert "acct-1" in notification.message
    assert notification.payload["difference_count"] == 1


def test_reconciliation_hook_payload_serializes_decimals_and_excludes_secret_fields() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "0.7"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    plan = build_reconciliation_hook_plan(report)
    payload = plan.audit_entry.payload
    differences = payload["differences"]

    assert isinstance(differences, list)
    assert differences[0]["exchange_database_delta"] == "0.3"
    assert differences[0]["database_target_delta"] == "-0.3"
    payload_text = str(payload).lower()
    assert "api_secret" not in payload_text
    assert "passphrase" not in payload_text
    assert "signature" not in payload_text


def test_build_reconciliation_hook_plan_supports_reserved_notification_channels() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("ETHUSDT", "3"),),
        database_positions=(snapshot("ETHUSDT", "0"),),
        target_positions=(snapshot("ETHUSDT", "0"),),
        critical_threshold=Decimal("1"),
    )

    plan = build_reconciliation_hook_plan(
        report,
        notification_channels=(
            ReconciliationNotificationChannel.INTERNAL,
            ReconciliationNotificationChannel.EMAIL,
            ReconciliationNotificationChannel.WEBHOOK,
        ),
    )

    assert plan.audit_entry.severity == PositionReconciliationSeverity.CRITICAL
    assert tuple(item.channel for item in plan.notifications) == (
        ReconciliationNotificationChannel.INTERNAL,
        ReconciliationNotificationChannel.EMAIL,
        ReconciliationNotificationChannel.WEBHOOK,
    )
    assert all(item.title == "Position reconciliation CRITICAL" for item in plan.notifications)
