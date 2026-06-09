from decimal import Decimal

from app.services.position_reconciliation import (
    PositionQuantitySnapshot,
    PositionReconciliationSeverity,
    PositionReconciliationStatus,
    reconcile_position_snapshots,
)


def snapshot(symbol: str, quantity: str) -> PositionQuantitySnapshot:
    return PositionQuantitySnapshot(symbol=symbol, quantity=Decimal(quantity))


def test_reconcile_position_snapshots_matches_when_all_sources_agree() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    assert report.status == PositionReconciliationStatus.MATCHED
    assert report.severity == PositionReconciliationSeverity.OK
    assert report.differences == ()
    assert report.auto_fix_allowed is False


def test_reconcile_position_snapshots_detects_exchange_database_and_target_drift() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1"),),
        database_positions=(snapshot("BTCUSDT", "0.7"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
        critical_threshold=Decimal("1"),
    )

    assert report.status == PositionReconciliationStatus.DRIFT_DETECTED
    assert report.severity == PositionReconciliationSeverity.WARNING
    assert len(report.differences) == 1
    difference = report.differences[0]
    assert difference.symbol == "BTCUSDT"
    assert difference.exchange_database_delta == Decimal("0.3")
    assert difference.exchange_target_delta == Decimal("0")
    assert difference.database_target_delta == Decimal("-0.3")
    assert difference.severity == PositionReconciliationSeverity.WARNING
    assert difference.reasons == (
        "exchange position differs from database position",
        "database position differs from target position",
    )


def test_reconcile_position_snapshots_marks_large_drift_as_critical() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("ETHUSDT", "3"),),
        database_positions=(snapshot("ETHUSDT", "0"),),
        target_positions=(snapshot("ETHUSDT", "0"),),
        critical_threshold=Decimal("1"),
    )

    assert report.status == PositionReconciliationStatus.DRIFT_DETECTED
    assert report.severity == PositionReconciliationSeverity.CRITICAL
    assert report.differences[0].severity == PositionReconciliationSeverity.CRITICAL


def test_reconcile_position_snapshots_respects_quantity_tolerance() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "1.00000001"),),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
        quantity_tolerance=Decimal("0.0000001"),
    )

    assert report.status == PositionReconciliationStatus.MATCHED
    assert report.differences == ()


def test_reconcile_position_snapshots_detects_missing_symbol_in_one_source() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("BTCUSDT", "0"),),
        database_positions=(),
        target_positions=(snapshot("ETHUSDT", "2"),),
        critical_threshold=Decimal("1"),
    )

    assert report.status == PositionReconciliationStatus.DRIFT_DETECTED
    assert report.severity == PositionReconciliationSeverity.CRITICAL
    assert tuple(item.symbol for item in report.differences) == ("ETHUSDT",)
    assert report.differences[0].exchange_target_delta == Decimal("-2")


def test_reconcile_position_snapshots_normalizes_symbols_and_combines_duplicates() -> None:
    report = reconcile_position_snapshots(
        user_id="user-1",
        exchange_account_id="acct-1",
        exchange_positions=(snapshot("btcusdt", "0.4"), snapshot("BTCUSDT", "0.6")),
        database_positions=(snapshot("BTCUSDT", "1"),),
        target_positions=(snapshot("BTCUSDT", "1"),),
    )

    assert report.status == PositionReconciliationStatus.MATCHED
    assert report.differences == ()
