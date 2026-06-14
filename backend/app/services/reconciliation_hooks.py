from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.services.position_reconciliation import (
    PositionReconciliationDifference,
    PositionReconciliationReport,
    PositionReconciliationSeverity,
    PositionReconciliationStatus,
)


class ReconciliationNotificationChannel(StrEnum):
    INTERNAL = "INTERNAL"
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class ReconciliationDriftAlertRuntime(Protocol):
    def notify_reconciliation_drift(
        self,
        *,
        status: str,
        severity: str,
        difference_count: int,
    ) -> tuple[object, ...]: ...


@dataclass(frozen=True)
class ReconciliationAuditEntryPlan:
    user_id: str
    exchange_account_id: str
    action: str
    severity: PositionReconciliationSeverity
    payload: dict[str, object]


@dataclass(frozen=True)
class ReconciliationSystemEventPlan:
    event_type: str
    severity: PositionReconciliationSeverity
    payload: dict[str, object]


@dataclass(frozen=True)
class ReconciliationNotificationPlan:
    channel: ReconciliationNotificationChannel
    severity: PositionReconciliationSeverity
    title: str
    message: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ReconciliationHookPlan:
    audit_entry: ReconciliationAuditEntryPlan
    system_event: ReconciliationSystemEventPlan | None
    notifications: tuple[ReconciliationNotificationPlan, ...]
    auto_fix_allowed: bool = False


def build_reconciliation_hook_plan(
    report: PositionReconciliationReport,
    *,
    notification_channels: tuple[ReconciliationNotificationChannel, ...] = (
        ReconciliationNotificationChannel.INTERNAL,
    ),
    alert_runtime: ReconciliationDriftAlertRuntime | None = None,
) -> ReconciliationHookPlan:
    payload = _report_payload(report)
    is_drift = report.status == PositionReconciliationStatus.DRIFT_DETECTED
    action = (
        "position_reconciliation.drift_detected"
        if is_drift
        else "position_reconciliation.matched"
    )
    audit_entry = ReconciliationAuditEntryPlan(
        user_id=report.user_id,
        exchange_account_id=report.exchange_account_id,
        action=action,
        severity=report.severity,
        payload=payload,
    )
    system_event = _system_event_for_drift(report=report, payload=payload) if is_drift else None
    notifications = (
        _notification_for_channel(channel=channel, report=report, payload=payload)
        for channel in notification_channels
        if is_drift
    )
    if is_drift:
        _notify_reconciliation_drift(alert_runtime=alert_runtime, report=report)
    return ReconciliationHookPlan(
        audit_entry=audit_entry,
        system_event=system_event,
        notifications=tuple(notifications),
        auto_fix_allowed=False,
    )


def _notify_reconciliation_drift(
    *,
    alert_runtime: ReconciliationDriftAlertRuntime | None,
    report: PositionReconciliationReport,
) -> None:
    if alert_runtime is None:
        return
    alert_runtime.notify_reconciliation_drift(
        status=report.status.value,
        severity=report.severity.value,
        difference_count=len(report.differences),
    )


def _system_event_for_drift(
    *,
    report: PositionReconciliationReport,
    payload: dict[str, object],
) -> ReconciliationSystemEventPlan:
    return ReconciliationSystemEventPlan(
        event_type="position_reconciliation.drift_detected",
        severity=report.severity,
        payload=payload,
    )


def _notification_for_channel(
    *,
    channel: ReconciliationNotificationChannel,
    report: PositionReconciliationReport,
    payload: dict[str, object],
) -> ReconciliationNotificationPlan:
    return ReconciliationNotificationPlan(
        channel=channel,
        severity=report.severity,
        title=f"Position reconciliation {report.severity.value}",
        message=(
            "Position reconciliation detected "
            f"{len(report.differences)} drifted symbol(s) for account "
            f"{report.exchange_account_id}."
        ),
        payload=payload,
    )


def _report_payload(report: PositionReconciliationReport) -> dict[str, object]:
    return {
        "user_id": report.user_id,
        "exchange_account_id": report.exchange_account_id,
        "status": report.status.value,
        "severity": report.severity.value,
        "difference_count": len(report.differences),
        "auto_fix_allowed": False,
        "differences": [_difference_payload(item) for item in report.differences],
    }


def _difference_payload(
    difference: PositionReconciliationDifference,
) -> dict[str, object]:
    return {
        "symbol": difference.symbol,
        "exchange_quantity": str(difference.exchange_quantity),
        "database_quantity": str(difference.database_quantity),
        "target_quantity": str(difference.target_quantity),
        "exchange_database_delta": str(difference.exchange_database_delta),
        "exchange_target_delta": str(difference.exchange_target_delta),
        "database_target_delta": str(difference.database_target_delta),
        "severity": difference.severity.value,
        "reasons": list(difference.reasons),
    }
