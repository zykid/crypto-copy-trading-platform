from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import (
    OrderExecution,
    OrderExecutionStatus,
    OrderExecutionTransition,
    OrderSide,
    OrderType,
)
from app.exchanges.mock import MockExchange
from app.services.exchange_accounts import create_account
from app.services.order_engine import execute_signal_for_account
from app.services.position_engine import apply_fill, calculate_delta, get_or_create_position
from app.services.risk_engine import (
    RiskOrderInput,
    check_order_risk,
    get_or_create_risk_settings,
    update_risk_settings,
)
from app.services.signal_engine import create_manual_signal
from app.services.users import create_user


class CapturingEmergencyStopRuntime:
    def __init__(self) -> None:
        self.scopes: list[str] = []

    def notify_emergency_stop_enabled(self, *, scope: str) -> tuple[object, ...]:
        self.scopes.append(scope)
        return ()


class CapturingOrderFailureRuntime:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def notify_order_failure(
        self,
        *,
        status: str,
        failure_type: str,
    ) -> tuple[object, ...]:
        self.events.append(
            {
                "status": status,
                "failure_type": failure_type,
            }
        )
        return ()


def test_position_engine_calculates_delta_not_full_target() -> None:
    delta = calculate_delta(
        symbol="BTCUSDT",
        current_quantity=Decimal("0.7"),
        target_quantity=Decimal("1"),
    )

    assert delta.side == OrderSide.BUY
    assert delta.delta_quantity == Decimal("0.3")


def test_risk_engine_rejects_disabled_trading_and_blocked_symbol(db_session: Session) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    account = create_account(
        db_session,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "mock",
            "trading_enabled": False,
        },
    )
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    settings.blocked_symbols = ["BTCUSDT"]
    db_session.commit()

    result = check_order_risk(
        account=account,
        settings=settings,
        order=RiskOrderInput(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
        ),
    )

    assert result.decision.value == "REJECTED"
    assert "exchange account trading is disabled" in result.reasons
    assert "risk settings trading is disabled" in result.reasons
    assert "symbol is blocked" in result.reasons


def test_risk_settings_disable_sends_emergency_stop_alert(db_session: Session) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    alert_runtime = CapturingEmergencyStopRuntime()

    update_risk_settings(
        db_session,
        settings,
        {"trading_enabled": False},
        alert_runtime=alert_runtime,
    )

    assert alert_runtime.scopes == ["account"]


def test_risk_settings_repeated_disable_does_not_send_emergency_stop_alert(
    db_session: Session,
) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    alert_runtime = CapturingEmergencyStopRuntime()

    update_risk_settings(
        db_session,
        settings,
        {"trading_enabled": False},
        alert_runtime=alert_runtime,
    )
    update_risk_settings(
        db_session,
        settings,
        {"trading_enabled": False},
        alert_runtime=alert_runtime,
    )

    assert alert_runtime.scopes == ["account"]


def test_risk_settings_disable_without_alert_runtime_keeps_existing_behavior(
    db_session: Session,
) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )

    updated = update_risk_settings(
        db_session,
        settings,
        {"trading_enabled": False},
    )

    assert updated.trading_enabled is False


def test_order_engine_executes_mock_order_and_updates_position(db_session: Session) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=None,
        quantity=Decimal("0.25"),
        target_position_quantity=None,
    )

    execution = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
    )
    position = get_or_create_position(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        symbol="BTCUSDT",
    )

    assert execution.status == OrderExecutionStatus.FILLED
    assert execution.exchange_order_id is not None
    assert execution.risk_result == {"decision": "PASSED", "reasons": []}
    assert position.quantity == Decimal("0.25")
    transitions = db_session.scalars(
        select(OrderExecutionTransition)
        .where(OrderExecutionTransition.order_execution_id == execution.id)
        .order_by(OrderExecutionTransition.sequence_number)
    ).all()
    assert [transition.to_status for transition in transitions] == [
        "CREATED",
        "RISK_PASSED",
        "SUBMITTED",
        "FILLED",
    ]


def test_order_engine_alerts_on_risk_rejected_terminal_failure(
    db_session: Session,
) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    settings.trading_enabled = False
    db_session.commit()
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=Decimal("100"),
        quantity=Decimal("1"),
        target_position_quantity=None,
    )
    alert_runtime = CapturingOrderFailureRuntime()

    execution = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
        alert_runtime=alert_runtime,
    )

    assert execution.status == OrderExecutionStatus.FAILED
    assert alert_runtime.events == [
        {
            "status": "FAILED",
            "failure_type": "risk_rejected",
        }
    ]


def test_order_failure_alert_omits_sensitive_execution_fields(
    db_session: Session,
) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    settings.trading_enabled = False
    db_session.commit()
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=Decimal("100"),
        quantity=Decimal("1"),
        target_position_quantity=None,
    )
    alert_runtime = CapturingOrderFailureRuntime()

    execution = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
        alert_runtime=alert_runtime,
    )

    event_text = str(alert_runtime.events[0])
    assert execution.exchange_account_id not in event_text
    assert execution.signal_id not in event_text
    assert execution.client_order_id not in event_text
    assert "BTCUSDT" not in event_text
    assert "100" not in event_text
    assert "1" not in event_text


def test_order_engine_target_position_uses_delta_quantity(db_session: Session) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    apply_fill(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.7"),
    )
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=None,
        quantity=None,
        target_position_quantity=Decimal("1"),
    )

    execution = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
    )

    assert execution.quantity == Decimal("0.3")
    assert execution.side == OrderSide.BUY


def test_order_engine_is_idempotent_per_signal_and_account(db_session: Session) -> None:
    user, account = _create_enabled_user_and_account(db_session)
    signal = create_manual_signal(
        db_session,
        user_id=user.id,
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        price=None,
        quantity=Decimal("1"),
        target_position_quantity=None,
    )

    first = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
    )
    second = execute_signal_for_account(
        db_session,
        user_id=user.id,
        signal_id=signal.id,
        exchange_account_id=account.id,
        exchange=MockExchange(),
    )
    executions = db_session.scalars(select(OrderExecution)).all()

    assert first.id == second.id
    assert len(executions) == 1


def _create_enabled_user_and_account(db_session: Session):
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    account = create_account(
        db_session,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "mock",
            "trading_enabled": True,
        },
    )
    settings = get_or_create_risk_settings(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    settings.trading_enabled = True
    settings.min_order_quantity = Decimal("0.0001")
    settings.max_order_quantity = Decimal("100")
    db_session.commit()
    db_session.refresh(settings)
    return user, account
