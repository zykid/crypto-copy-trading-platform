from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.postgres_restore_drill import (  # noqa: E402
    PostgresRestoreDrillError,
    verify_plain_sql_backup,
)

BACKUP_FILE_PATTERN = re.compile(r"^backup_\d{8}\.sql$")
DEFAULT_SERVICE_UNIT = "trading-postgres-backup.service"
DEFAULT_TIMER_UNIT = "trading-postgres-backup.timer"
SYSTEMCTL_TIMER_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "SubState",
    "NextElapseUSecRealtime",
    "LastTriggerUSec",
)
SYSTEMCTL_SERVICE_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainStatus",
)


class SystemdBackupTimerVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SystemdBackupTimerVerificationReport:
    timer_unit: str
    service_unit: str
    timer_active_state: str
    service_result: str
    backup_file: Path
    backup_size_bytes: int


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the production PostgreSQL backup systemd timer and latest dump."
    )
    parser.add_argument("--backup-dir", required=True, help="Directory containing backup_YYYYMMDD.sql")
    parser.add_argument("--timer-unit", default=DEFAULT_TIMER_UNIT)
    parser.add_argument("--service-unit", default=DEFAULT_SERVICE_UNIT)
    args = parser.parse_args()

    try:
        report = verify_systemd_backup_timer(
            backup_dir=Path(args.backup_dir),
            timer_unit=args.timer_unit,
            service_unit=args.service_unit,
        )
    except (PostgresRestoreDrillError, SystemdBackupTimerVerificationError) as exc:
        print(f"Systemd backup timer verification failed: {exc}", file=sys.stderr)
        return 1

    print("Systemd backup timer verification passed")
    print(f"Timer unit: {report.timer_unit} ({report.timer_active_state})")
    print(f"Service unit: {report.service_unit} (result={report.service_result})")
    print(f"Latest backup: {report.backup_file}")
    print(f"Size bytes: {report.backup_size_bytes}")
    return 0


def verify_systemd_backup_timer(
    *,
    backup_dir: Path,
    timer_unit: str = DEFAULT_TIMER_UNIT,
    service_unit: str = DEFAULT_SERVICE_UNIT,
) -> SystemdBackupTimerVerificationReport:
    timer_properties = parse_systemctl_show(
        run_systemctl_show(timer_unit, SYSTEMCTL_TIMER_PROPERTIES)
    )
    service_properties = parse_systemctl_show(
        run_systemctl_show(service_unit, SYSTEMCTL_SERVICE_PROPERTIES)
    )
    validate_systemd_properties(
        timer_properties=timer_properties,
        service_properties=service_properties,
    )

    backup_file = find_latest_backup_file(backup_dir)
    if backup_file is None:
        raise SystemdBackupTimerVerificationError(
            f"no backup_YYYYMMDD.sql files found in {backup_dir}"
        )
    backup_result = verify_plain_sql_backup(backup_file)

    return SystemdBackupTimerVerificationReport(
        timer_unit=timer_unit,
        service_unit=service_unit,
        timer_active_state=timer_properties.get("ActiveState", "unknown"),
        service_result=service_properties.get("Result", "unknown"),
        backup_file=backup_result.path,
        backup_size_bytes=backup_result.size_bytes,
    )


def run_systemctl_show(unit: str, properties: tuple[str, ...]) -> str:
    command = ["systemctl", "show", unit]
    for property_name in properties:
        command.append(f"--property={property_name}")
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def parse_systemctl_show(output: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        properties[key.strip()] = value.strip()
    return properties


def validate_systemd_properties(
    *,
    timer_properties: dict[str, str],
    service_properties: dict[str, str],
) -> None:
    if timer_properties.get("LoadState") != "loaded":
        raise SystemdBackupTimerVerificationError("backup timer unit is not loaded")
    if timer_properties.get("ActiveState") != "active":
        raise SystemdBackupTimerVerificationError("backup timer unit is not active")
    if service_properties.get("LoadState") != "loaded":
        raise SystemdBackupTimerVerificationError("backup service unit is not loaded")
    if service_properties.get("Result") not in {"", "success"}:
        raise SystemdBackupTimerVerificationError("backup service last result is not success")


def find_latest_backup_file(backup_dir: Path) -> Path | None:
    resolved_dir = backup_dir.expanduser().resolve()
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise SystemdBackupTimerVerificationError(f"backup directory does not exist: {resolved_dir}")

    candidates = tuple(
        path for path in resolved_dir.iterdir() if path.is_file() and BACKUP_FILE_PATTERN.match(path.name)
    )
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


if __name__ == "__main__":
    raise SystemExit(main())
