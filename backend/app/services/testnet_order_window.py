from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import RiskSetting
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account
from app.services.testnet_order_gate import check_testnet_order_gate


class OrderWindowPlanStatus(StrEnum):
    READY_FOR_SEPARATE_APPROVAL = "READY_FOR_SEPARATE_APPROVAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class OrderWindowPlanState:
    exchange_name: ExchangeName
    account_mode: AccountMode
    testnet_adapters_enabled: bool
    exchange_account_trading_enabled: bool
    risk_settings_exist: bool
    risk_trading_enabled: bool
    api_key_configured: bool


@dataclass(frozen=True)
class OrderWindowPlan:
    exchange_account_id: str
    status: OrderWindowPlanStatus
    state: OrderWindowPlanState
    blocked_reasons: tuple[str, ...]
    required_operator_steps: tuple[str, ...]
    mutations_allowed: bool = False
    order_submission_authorized: bool = False


def build_testnet_order_window_plan(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    testnet_adapters_enabled: bool,
) -> OrderWindowPlan:
    account = get_owned_account(
        db,
        user_id=user_id,
        account_id=exchange_account_id,
    )
    if account is None:
        raise ValueError("account not found")

    risk_settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user_id,
            RiskSetting.exchange_account_id == account.id,
        )
    )
    secret_metadata = get_api_key_secret_metadata(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    risk_trading_enabled = risk_settings.trading_enabled if risk_settings else False
    api_key_configured = secret_metadata is not None

    gate_result = check_testnet_order_gate(
        exchange_name=account.exchange_name,
        account_mode=account.account_mode,
        testnet_adapters_enabled=testnet_adapters_enabled,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_trading_enabled=risk_trading_enabled,
        api_key_configured=api_key_configured,
        manual_testnet_order_enable_confirmed=False,
    )
    blocked_reasons = _pre_window_blocked_reasons(
        account_mode=account.account_mode,
        risk_settings_exist=risk_settings is not None,
        api_key_configured=api_key_configured,
    )
    status = (
        OrderWindowPlanStatus.READY_FOR_SEPARATE_APPROVAL
        if not blocked_reasons
        else OrderWindowPlanStatus.BLOCKED
    )

    return OrderWindowPlan(
        exchange_account_id=account.id,
        status=status,
        state=OrderWindowPlanState(
            exchange_name=account.exchange_name,
            account_mode=account.account_mode,
            testnet_adapters_enabled=testnet_adapters_enabled,
            exchange_account_trading_enabled=account.trading_enabled,
            risk_settings_exist=risk_settings is not None,
            risk_trading_enabled=risk_trading_enabled,
            api_key_configured=api_key_configured,
        ),
        blocked_reasons=blocked_reasons,
        required_operator_steps=_required_operator_steps(gate_result.reasons),
    )


def _pre_window_blocked_reasons(
    *,
    account_mode: AccountMode,
    risk_settings_exist: bool,
    api_key_configured: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if account_mode != AccountMode.TESTNET:
        reasons.append("account mode must be TESTNET before preparing an order window")
    if not risk_settings_exist:
        reasons.append("risk settings must exist before preparing an order window")
    if not api_key_configured:
        reasons.append("encrypted API key metadata must exist before preparing an order window")
    return tuple(reasons)


def _required_operator_steps(gate_reasons: tuple[str, ...]) -> tuple[str, ...]:
    return (
        "complete docs/phase-3-testnet-order-admission-checklist.md",
        "record a separate explicit approval for a bounded TESTNET order window",
        "temporarily set TESTNET_ADAPTERS_ENABLED=true only during the approved window",
        "temporarily enable exchange_account.trading_enabled for the selected account only",
        "temporarily enable risk_settings.trading_enabled for the selected account only",
        "record manual testnet order enable confirmation in append-only audit logs",
        "submit at most the separately approved test order with an idempotent client_order_id",
        "restore TESTNET_ADAPTERS_ENABLED=false and both trading_enabled flags to false",
        f"current gate still blocks submission: {'; '.join(gate_reasons)}",
    )
