from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.services.position_reconciliation import (
    PositionReconciliationDifference,
    PositionReconciliationReport,
    PositionReconciliationSeverity,
    PositionReconciliationStatus,
)


class ReconciliationRepairStatus(StrEnum):
    DISABLED = "DISABLED"
    NO_DRIFT = "NO_DRIFT"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"


class ReconciliationRepairAction(StrEnum):
    BUY_TO_TARGET = "BUY_TO_TARGET"
    SELL_TO_TARGET = "SELL_TO_TARGET"
    REVIEW_DATABASE_POSITION = "REVIEW_DATABASE_POSITION"


@dataclass(frozen=True)
class ReconciliationRepairSettings:
    proposal_generation_enabled: bool = False
    execution_enabled: bool = False


@dataclass(frozen=True)
class ReconciliationRepairProposal:
    symbol: str
    action: ReconciliationRepairAction
    quantity_delta: Decimal
    exchange_quantity: Decimal
    database_quantity: Decimal
    target_quantity: Decimal
    severity: PositionReconciliationSeverity
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReconciliationRepairPlan:
    user_id: str
    exchange_account_id: str
    status: ReconciliationRepairStatus
    proposals: tuple[ReconciliationRepairProposal, ...]
    auto_fix_allowed: bool = False
    execution_allowed: bool = False


def build_reconciliation_repair_plan(
    report: PositionReconciliationReport,
    *,
    settings: ReconciliationRepairSettings | None = None,
) -> ReconciliationRepairPlan:
    repair_settings = settings or ReconciliationRepairSettings()
    if not repair_settings.proposal_generation_enabled:
        return _plan(
            report,
            status=ReconciliationRepairStatus.DISABLED,
            proposals=(),
        )
    if report.status == PositionReconciliationStatus.MATCHED:
        return _plan(
            report,
            status=ReconciliationRepairStatus.NO_DRIFT,
            proposals=(),
        )

    proposals = tuple(
        proposal
        for difference in report.differences
        if (proposal := _proposal_for_difference(difference)) is not None
    )
    if repair_settings.execution_enabled:
        return _plan(
            report,
            status=ReconciliationRepairStatus.EXECUTION_BLOCKED,
            proposals=proposals,
        )
    return _plan(
        report,
        status=ReconciliationRepairStatus.PROPOSAL_CREATED,
        proposals=proposals,
    )


def _proposal_for_difference(
    difference: PositionReconciliationDifference,
) -> ReconciliationRepairProposal | None:
    target_exchange_delta = difference.target_quantity - difference.exchange_quantity
    if target_exchange_delta > Decimal("0"):
        return _proposal(
            difference,
            action=ReconciliationRepairAction.BUY_TO_TARGET,
            quantity_delta=target_exchange_delta,
        )
    if target_exchange_delta < Decimal("0"):
        return _proposal(
            difference,
            action=ReconciliationRepairAction.SELL_TO_TARGET,
            quantity_delta=abs(target_exchange_delta),
        )
    if difference.database_target_delta != Decimal("0"):
        return _proposal(
            difference,
            action=ReconciliationRepairAction.REVIEW_DATABASE_POSITION,
            quantity_delta=abs(difference.database_target_delta),
        )
    return None


def _proposal(
    difference: PositionReconciliationDifference,
    *,
    action: ReconciliationRepairAction,
    quantity_delta: Decimal,
) -> ReconciliationRepairProposal:
    return ReconciliationRepairProposal(
        symbol=difference.symbol,
        action=action,
        quantity_delta=quantity_delta,
        exchange_quantity=difference.exchange_quantity,
        database_quantity=difference.database_quantity,
        target_quantity=difference.target_quantity,
        severity=difference.severity,
        reasons=difference.reasons,
    )


def _plan(
    report: PositionReconciliationReport,
    *,
    status: ReconciliationRepairStatus,
    proposals: tuple[ReconciliationRepairProposal, ...],
) -> ReconciliationRepairPlan:
    return ReconciliationRepairPlan(
        user_id=report.user_id,
        exchange_account_id=report.exchange_account_id,
        status=status,
        proposals=proposals,
        auto_fix_allowed=False,
        execution_allowed=False,
    )
