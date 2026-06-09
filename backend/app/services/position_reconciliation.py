from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class PositionReconciliationStatus(StrEnum):
    MATCHED = "MATCHED"
    DRIFT_DETECTED = "DRIFT_DETECTED"


class PositionReconciliationSeverity(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PositionQuantitySnapshot:
    symbol: str
    quantity: Decimal


@dataclass(frozen=True)
class PositionReconciliationDifference:
    symbol: str
    exchange_quantity: Decimal
    database_quantity: Decimal
    target_quantity: Decimal
    exchange_database_delta: Decimal
    exchange_target_delta: Decimal
    database_target_delta: Decimal
    severity: PositionReconciliationSeverity
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PositionReconciliationReport:
    user_id: str
    exchange_account_id: str
    status: PositionReconciliationStatus
    severity: PositionReconciliationSeverity
    differences: tuple[PositionReconciliationDifference, ...]
    auto_fix_allowed: bool = False


def reconcile_position_snapshots(
    *,
    user_id: str,
    exchange_account_id: str,
    exchange_positions: tuple[PositionQuantitySnapshot, ...],
    database_positions: tuple[PositionQuantitySnapshot, ...],
    target_positions: tuple[PositionQuantitySnapshot, ...],
    quantity_tolerance: Decimal = Decimal("0"),
    critical_threshold: Decimal = Decimal("1"),
) -> PositionReconciliationReport:
    exchange_by_symbol = _normalize_snapshots(exchange_positions)
    database_by_symbol = _normalize_snapshots(database_positions)
    target_by_symbol = _normalize_snapshots(target_positions)
    symbols = tuple(sorted(exchange_by_symbol | database_by_symbol | target_by_symbol))

    differences = tuple(
        _difference_for_symbol(
            symbol=symbol,
            exchange_quantity=exchange_by_symbol.get(symbol, Decimal("0")),
            database_quantity=database_by_symbol.get(symbol, Decimal("0")),
            target_quantity=target_by_symbol.get(symbol, Decimal("0")),
            quantity_tolerance=quantity_tolerance,
            critical_threshold=critical_threshold,
        )
        for symbol in symbols
    )
    drifted = tuple(item for item in differences if item.severity != PositionReconciliationSeverity.OK)
    severity = _report_severity(drifted)
    return PositionReconciliationReport(
        user_id=user_id,
        exchange_account_id=exchange_account_id,
        status=(
            PositionReconciliationStatus.DRIFT_DETECTED
            if drifted
            else PositionReconciliationStatus.MATCHED
        ),
        severity=severity,
        differences=drifted,
        auto_fix_allowed=False,
    )


def _normalize_snapshots(
    snapshots: tuple[PositionQuantitySnapshot, ...]
) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for snapshot in snapshots:
        symbol = snapshot.symbol.upper()
        normalized[symbol] = normalized.get(symbol, Decimal("0")) + snapshot.quantity
    return normalized


def _difference_for_symbol(
    *,
    symbol: str,
    exchange_quantity: Decimal,
    database_quantity: Decimal,
    target_quantity: Decimal,
    quantity_tolerance: Decimal,
    critical_threshold: Decimal,
) -> PositionReconciliationDifference:
    exchange_database_delta = exchange_quantity - database_quantity
    exchange_target_delta = exchange_quantity - target_quantity
    database_target_delta = database_quantity - target_quantity
    reasons = _difference_reasons(
        exchange_database_delta=exchange_database_delta,
        exchange_target_delta=exchange_target_delta,
        database_target_delta=database_target_delta,
        quantity_tolerance=quantity_tolerance,
    )
    severity = _difference_severity(
        deltas=(exchange_database_delta, exchange_target_delta, database_target_delta),
        reasons=reasons,
        critical_threshold=critical_threshold,
    )
    return PositionReconciliationDifference(
        symbol=symbol,
        exchange_quantity=exchange_quantity,
        database_quantity=database_quantity,
        target_quantity=target_quantity,
        exchange_database_delta=exchange_database_delta,
        exchange_target_delta=exchange_target_delta,
        database_target_delta=database_target_delta,
        severity=severity,
        reasons=reasons,
    )


def _difference_reasons(
    *,
    exchange_database_delta: Decimal,
    exchange_target_delta: Decimal,
    database_target_delta: Decimal,
    quantity_tolerance: Decimal,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _outside_tolerance(exchange_database_delta, quantity_tolerance):
        reasons.append("exchange position differs from database position")
    if _outside_tolerance(exchange_target_delta, quantity_tolerance):
        reasons.append("exchange position differs from target position")
    if _outside_tolerance(database_target_delta, quantity_tolerance):
        reasons.append("database position differs from target position")
    return tuple(reasons)


def _difference_severity(
    *,
    deltas: tuple[Decimal, Decimal, Decimal],
    reasons: tuple[str, ...],
    critical_threshold: Decimal,
) -> PositionReconciliationSeverity:
    if not reasons:
        return PositionReconciliationSeverity.OK
    if any(abs(delta) >= critical_threshold for delta in deltas):
        return PositionReconciliationSeverity.CRITICAL
    return PositionReconciliationSeverity.WARNING


def _report_severity(
    differences: tuple[PositionReconciliationDifference, ...]
) -> PositionReconciliationSeverity:
    if any(item.severity == PositionReconciliationSeverity.CRITICAL for item in differences):
        return PositionReconciliationSeverity.CRITICAL
    if differences:
        return PositionReconciliationSeverity.WARNING
    return PositionReconciliationSeverity.OK


def _outside_tolerance(delta: Decimal, tolerance: Decimal) -> bool:
    return abs(delta) > tolerance
