from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models.observability import AuditLog, SystemEvent

MAX_OBSERVABILITY_PAGE_SIZE = 100


@dataclass(frozen=True)
class AuditLogFilter:
    user_id: str | None = None
    exchange_account_id: str | None = None
    action: str | None = None
    severity: str | None = None
    limit: int = 50


@dataclass(frozen=True)
class SystemEventFilter:
    user_id: str | None = None
    exchange_account_id: str | None = None
    event_type: str | None = None
    severity: str | None = None
    limit: int = 50


class ObservabilityService:
    def list_audit_logs(
        self,
        db: Session,
        filters: AuditLogFilter,
    ) -> tuple[AuditLog, ...]:
        query = select(AuditLog)
        query = _apply_optional_filter(query, AuditLog.user_id, filters.user_id)
        query = _apply_optional_filter(
            query,
            AuditLog.exchange_account_id,
            filters.exchange_account_id,
        )
        query = _apply_optional_filter(query, AuditLog.action, filters.action)
        query = _apply_optional_filter(query, AuditLog.severity, filters.severity)
        query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(
            _bounded_limit(filters.limit)
        )
        return tuple(db.scalars(query).all())

    def list_system_events(
        self,
        db: Session,
        filters: SystemEventFilter,
    ) -> tuple[SystemEvent, ...]:
        query = select(SystemEvent)
        query = _apply_optional_filter(query, SystemEvent.user_id, filters.user_id)
        query = _apply_optional_filter(
            query,
            SystemEvent.exchange_account_id,
            filters.exchange_account_id,
        )
        query = _apply_optional_filter(query, SystemEvent.event_type, filters.event_type)
        query = _apply_optional_filter(query, SystemEvent.severity, filters.severity)
        query = query.order_by(SystemEvent.created_at.desc(), SystemEvent.id.desc()).limit(
            _bounded_limit(filters.limit)
        )
        return tuple(db.scalars(query).all())


def _apply_optional_filter(query: Select, column, value: str | None) -> Select:
    if value is None:
        return query
    return query.where(column == value)


def _bounded_limit(limit: int) -> int:
    return min(max(limit, 1), MAX_OBSERVABILITY_PAGE_SIZE)


observability_service = ObservabilityService()
