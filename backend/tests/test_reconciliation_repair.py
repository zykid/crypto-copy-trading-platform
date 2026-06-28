from dataclasses import asdict
from decimal import Decimal

from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    reconcile_position_snapshots,
)
from app.services.reconciliation_repair import (
    ReconciliationRepairAction,
    ReconciliationRepairSettings,
    ReconciliationRepairStatus,
    build_reconciliation_repair_plan,
)


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def drift_report():
    return reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "0.7"),),
        database_positions=(snapshot("BTCUSDT", "0.7"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )


def test_reconciliation_repair_plan_is_disabled_by_default() -> None:
    plan = build_reconciliation_repair_plan(drift_report())

    assert plan.status == ReconciliationRepairStatus.DISABLED
    assert plan.proposals == ()
    assert plan.auto_fix_allowed is False
    assert plan.execution_allowed is False


def test_reconciliation_repair_plan_returns_no_drift_for_matched_report() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    plan = build_reconciliation_repair_plan(
        report,
        settings=ReconciliationRepairSettings(proposal_generation_enabled=True),
    )

    assert plan.status == ReconciliationRepairStatus.NO_DRIFT
    assert plan.proposals == ()
    assert plan.auto_fix_allowed is False
    assert plan.execution_allowed is False


def test_reconciliation_repair_plan_creates_buy_proposal_without_execution() -> None:
    plan = build_reconciliation_repair_plan(
        drift_report(),
        settings=ReconciliationRepairSettings(proposal_generation_enabled=True),
    )

    assert plan.status == ReconciliationRepairStatus.PROPOSAL_CREATED
    assert plan.auto_fix_allowed is False
    assert plan.execution_allowed is False
    assert len(plan.proposals) == 1
    proposal = plan.proposals[0]
    assert proposal.symbol == "BTCUSDT"
    assert proposal.action == ReconciliationRepairAction.BUY_TO_TARGET
    assert proposal.quantity_delta == Decimal("0.3")
    assert proposal.exchange_quantity == Decimal("0.7")
    assert proposal.target_quantity == Decimal("1")


def test_reconciliation_repair_plan_creates_sell_proposal_without_execution() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("ETHUSDT", "3"),),
        database_positions=(snapshot("ETHUSDT", "3"),),
        target_positions=(snapshot("ETHUSDT", "1.5"),),
    )

    plan = build_reconciliation_repair_plan(
        report,
        settings=ReconciliationRepairSettings(proposal_generation_enabled=True),
    )

    assert plan.status == ReconciliationRepairStatus.PROPOSAL_CREATED
    assert plan.proposals[0].action == ReconciliationRepairAction.SELL_TO_TARGET
    assert plan.proposals[0].quantity_delta == Decimal("1.5")
    assert plan.execution_allowed is False


def test_reconciliation_repair_plan_blocks_requested_execution() -> None:
    plan = build_reconciliation_repair_plan(
        drift_report(),
        settings=ReconciliationRepairSettings(
            proposal_generation_enabled=True,
            execution_enabled=True,
        ),
    )

    assert plan.status == ReconciliationRepairStatus.EXECUTION_BLOCKED
    assert len(plan.proposals) == 1
    assert plan.auto_fix_allowed is False
    assert plan.execution_allowed is False


def test_reconciliation_repair_plan_omits_secret_material() -> None:
    plan = build_reconciliation_repair_plan(
        drift_report(),
        settings=ReconciliationRepairSettings(proposal_generation_enabled=True),
    )

    serialized = str(asdict(plan)).lower()
    forbidden = ("api_key", "api_secret", "passphrase", "signature", "secret")
    assert all(item not in serialized for item in forbidden)
