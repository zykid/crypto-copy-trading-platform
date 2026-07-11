from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.exchange_account import ExchangeAccount
from app.db.models.observability import AuditLog, SystemEvent
from app.db.models.system_control import GLOBAL_SYSTEM_CONTROL_ID, SystemControl
from app.db.models.trading import RiskSetting
from app.db.models.user import User


class EmergencyStopEnabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmergencyStopState:
    enabled: bool
    reason: str | None
    changed_by_user_id: str | None
    changed_at: datetime


def get_emergency_stop_state(db: Session) -> EmergencyStopState:
    control = db.get(SystemControl, GLOBAL_SYSTEM_CONTROL_ID)
    if control is None:
        return EmergencyStopState(
            enabled=False,
            reason=None,
            changed_by_user_id=None,
            changed_at=datetime.now(UTC),
        )
    return _to_state(control)


def assert_new_orders_allowed(db: Session) -> None:
    control = db.get(SystemControl, GLOBAL_SYSTEM_CONTROL_ID)
    if control is not None and control.emergency_stop_enabled:
        raise EmergencyStopEnabledError("global emergency stop is enabled")


def set_emergency_stop(
    db: Session,
    *,
    enabled: bool,
    actor: User,
    reason: str,
) -> EmergencyStopState:
    clean_reason = " ".join(reason.split())[:500]
    control = db.scalar(
        select(SystemControl)
        .where(SystemControl.id == GLOBAL_SYSTEM_CONTROL_ID)
        .with_for_update()
    )
    if control is None:
        control = SystemControl(id=GLOBAL_SYSTEM_CONTROL_ID)
        db.add(control)
        db.flush()

    changed = control.emergency_stop_enabled != enabled
    control.emergency_stop_enabled = enabled
    control.reason = clean_reason
    control.changed_by_user_id = actor.id
    if enabled:
        db.execute(update(ExchangeAccount).values(trading_enabled=False))
        db.execute(update(RiskSetting).values(trading_enabled=False))

    action = "system.emergency_stop.activated" if enabled else "system.emergency_stop.deactivated"
    payload: dict[str, object] = {
        "scope": "global",
        "enabled": enabled,
        "reason": clean_reason,
        "state_changed": changed,
        "trading_flags_forced_off": enabled,
    }
    db.add(
        AuditLog(
            user_id=actor.id,
            exchange_account_id=None,
            action=action,
            severity="CRITICAL" if enabled else "WARNING",
            payload=payload,
        )
    )
    db.add(
        SystemEvent(
            user_id=actor.id,
            exchange_account_id=None,
            event_type=action,
            severity="CRITICAL" if enabled else "WARNING",
            payload=payload,
        )
    )
    db.commit()
    db.refresh(control)
    return _to_state(control)


def _to_state(control: SystemControl) -> EmergencyStopState:
    return EmergencyStopState(
        enabled=control.emergency_stop_enabled,
        reason=control.reason,
        changed_by_user_id=control.changed_by_user_id,
        changed_at=control.changed_at,
    )
