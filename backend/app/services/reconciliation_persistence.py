from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.observability import (
    AuditLog,
    InternalNotification,
    NotificationChannel,
    SystemEvent,
)
from app.services.notification_service import (
    InternalNotificationInput,
    NotificationEventType,
    notification_service,
)
from app.services.reconciliation_hooks import ReconciliationHookPlan


@dataclass(frozen=True)
class PersistedReconciliationHookPlan:
    audit_log: AuditLog
    system_event: SystemEvent | None
    internal_notifications: tuple[InternalNotification, ...]


def persist_reconciliation_hook_plan(
    db: Session,
    plan: ReconciliationHookPlan,
) -> PersistedReconciliationHookPlan:
    audit_log = AuditLog(
        user_id=plan.audit_entry.user_id,
        exchange_account_id=plan.audit_entry.exchange_account_id,
        action=plan.audit_entry.action,
        severity=plan.audit_entry.severity.value,
        payload=plan.audit_entry.payload,
    )
    db.add(audit_log)

    system_event = None
    if plan.system_event is not None:
        system_event = SystemEvent(
            user_id=plan.audit_entry.user_id,
            exchange_account_id=plan.audit_entry.exchange_account_id,
            event_type=plan.system_event.event_type,
            severity=plan.system_event.severity.value,
            payload=plan.system_event.payload,
        )
        db.add(system_event)

    internal_notifications = notification_service.create_preference_aware_internal_notifications(
        db,
        (
            InternalNotificationInput(
                user_id=plan.audit_entry.user_id,
                exchange_account_id=plan.audit_entry.exchange_account_id,
                channel=NotificationChannel(notification.channel.value),
                severity=notification.severity.value,
                title=notification.title,
                message=notification.message,
                payload=notification.payload,
                event_type=NotificationEventType.POSITION_DRIFT,
            )
            for notification in plan.notifications
        ),
    )
    db.flush()

    return PersistedReconciliationHookPlan(
        audit_log=audit_log,
        system_event=system_event,
        internal_notifications=internal_notifications,
    )
