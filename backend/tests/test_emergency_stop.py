from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeAccount, ExchangeName
from app.db.models.observability import AuditLog, SystemEvent
from app.db.models.trading import RiskSetting
from app.db.models.user import User, UserRole
from app.main import app
from app.schemas.system_control import EmergencyStopActivateRequest
from app.services.emergency_stop import (
    EmergencyStopEnabledError,
    assert_new_orders_allowed,
    get_emergency_stop_state,
    set_emergency_stop,
)


def _super_admin(db: Session) -> User:
    user = User(
        email="kill-switch-admin@example.com",
        username="kill_switch_admin",
        password_hash="unused",
        role=UserRole.SUPER_ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_global_emergency_stop_is_persistent_and_forces_trading_flags_off(
    db_session: Session,
) -> None:
    actor = _super_admin(db_session)
    account = ExchangeAccount(
        user_id=actor.id,
        exchange_name=ExchangeName.MOCK,
        account_label="Kill Switch Mock",
        account_mode=AccountMode.SIMULATION,
        trading_enabled=True,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(
        RiskSetting(
            user_id=actor.id,
            exchange_account_id=account.id,
            trading_enabled=True,
            max_single_order_notional=Decimal("100"),
            max_position_notional=Decimal("1000"),
            max_leverage=Decimal("1"),
            min_order_quantity=Decimal("0.001"),
            max_order_quantity=Decimal("10"),
            blocked_symbols=[],
        )
    )
    db_session.commit()

    state = set_emergency_stop(
        db_session,
        enabled=True,
        actor=actor,
        reason="Operator emergency drill",
    )

    assert state.enabled is True
    assert db_session.get(ExchangeAccount, account.id).trading_enabled is False
    risk = db_session.scalar(
        select(RiskSetting).where(RiskSetting.exchange_account_id == account.id)
    )
    assert risk is not None and risk.trading_enabled is False
    with pytest.raises(EmergencyStopEnabledError):
        assert_new_orders_allowed(db_session)
    assert db_session.scalars(select(AuditLog)).one().action == "system.emergency_stop.activated"
    event = db_session.scalars(select(SystemEvent)).one()
    assert event.event_type == "system.emergency_stop.activated"

    restored = set_emergency_stop(
        db_session,
        enabled=False,
        actor=actor,
        reason="Drill completed after review",
    )
    assert restored.enabled is False
    assert_new_orders_allowed(db_session)
    assert get_emergency_stop_state(db_session).reason == "Drill completed after review"


def test_emergency_stop_admin_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/system-control/emergency-stop" in paths
    assert "/api/v1/admin/system-control/emergency-stop/activate" in paths
    assert "/api/v1/admin/system-control/emergency-stop/deactivate" in paths


def test_emergency_stop_reason_rejects_whitespace_only_value() -> None:
    with pytest.raises(ValueError):
        EmergencyStopActivateRequest(reason="     ")
