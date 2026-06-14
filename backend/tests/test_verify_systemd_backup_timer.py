from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.backup.verify_systemd_backup_timer import (  # noqa: E402
    SystemdBackupTimerVerificationError,
    find_latest_backup_file,
    parse_systemctl_show,
    validate_systemd_properties,
)


def test_parse_systemctl_show_ignores_lines_without_properties() -> None:
    properties = parse_systemctl_show(
        "LoadState=loaded\n"
        "ignored line\n"
        "ActiveState=active\n"
        "Result=success\n"
    )

    assert properties == {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
    }


def test_validate_systemd_properties_accepts_loaded_active_timer() -> None:
    validate_systemd_properties(
        timer_properties={"LoadState": "loaded", "ActiveState": "active"},
        service_properties={"LoadState": "loaded", "Result": "success"},
    )


def test_validate_systemd_properties_rejects_inactive_timer() -> None:
    with pytest.raises(SystemdBackupTimerVerificationError, match="not active"):
        validate_systemd_properties(
            timer_properties={"LoadState": "loaded", "ActiveState": "inactive"},
            service_properties={"LoadState": "loaded", "Result": "success"},
        )


def test_validate_systemd_properties_rejects_failed_service_result() -> None:
    with pytest.raises(SystemdBackupTimerVerificationError, match="not success"):
        validate_systemd_properties(
            timer_properties={"LoadState": "loaded", "ActiveState": "active"},
            service_properties={"LoadState": "loaded", "Result": "exit-code"},
        )


def test_find_latest_backup_file_selects_newest_named_dump(tmp_path: Path) -> None:
    older = tmp_path / "backup_20260612.sql"
    newer = tmp_path / "backup_20260613.sql"
    ignored = tmp_path / "backup_latest.sql"
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")

    assert find_latest_backup_file(tmp_path) == newer.resolve()


def test_find_latest_backup_file_returns_none_without_matching_dump(tmp_path: Path) -> None:
    (tmp_path / "backup_latest.sql").write_text("ignored", encoding="utf-8")

    assert find_latest_backup_file(tmp_path) is None


def test_find_latest_backup_file_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(SystemdBackupTimerVerificationError, match="does not exist"):
        find_latest_backup_file(tmp_path / "missing")
