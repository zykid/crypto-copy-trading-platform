import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from app.services import external_alerts
from app.services.postgres_backup import PostgresBackupError


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backup" / "postgres_backup.py"
SECRET_VALUE = "super-secret-db-password"


def _load_backup_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("postgres_backup_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backup_script(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("POSTGRES_DB", "trading_prod")
    monkeypatch.setenv("POSTGRES_USER", "trading_prod")
    monkeypatch.setenv("POSTGRES_PASSWORD", SECRET_VALUE)
    return _load_backup_script()


def test_backup_failure_does_not_send_alert_when_channels_disabled(
    backup_script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    send_calls: list[object] = []

    def fail_backup(config: object) -> None:
        raise PostgresBackupError(f"pg_dump failed with {SECRET_VALUE}")

    def send_alert(config: object, event: object):
        send_calls.append((config, event))
        return ()

    monkeypatch.setattr(backup_script, "run_pg_dump_backup", fail_backup)
    monkeypatch.setattr(backup_script, "send_external_alert", send_alert)

    exit_code = backup_script.main(["--output-dir", "backups"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert send_calls == []
    assert "PostgreSQL backup failed: PostgresBackupError" in captured.err
    assert SECRET_VALUE not in captured.err


def test_backup_failure_sends_coarse_alert_when_webhook_enabled(
    backup_script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sent_events: list[external_alerts.ExternalAlertEvent] = []

    def fail_backup(config: object) -> None:
        raise PostgresBackupError(f"pg_dump failed with {SECRET_VALUE}")

    def send_alert(config: object, event: external_alerts.ExternalAlertEvent):
        sent_events.append(event)
        return (
            external_alerts.ExternalAlertDeliveryResult(
                channel=external_alerts.ExternalAlertChannel.WEBHOOK,
                delivered=True,
            ),
        )

    monkeypatch.setenv("WEBHOOK_ALERTS_ENABLED", "true")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://alerts.example.com/hook")
    monkeypatch.setattr(backup_script, "run_pg_dump_backup", fail_backup)
    monkeypatch.setattr(backup_script, "send_external_alert", send_alert)

    exit_code = backup_script.main(["--output-dir", "backups"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert len(sent_events) == 1
    event = sent_events[0]
    assert event.title == "PostgreSQL backup failed"
    assert event.message == "The scheduled PostgreSQL backup job failed."
    assert event.metadata == {
        "component": "postgres_backup",
        "error_type": "PostgresBackupError",
    }
    assert "PostgreSQL backup alert webhook: delivered" in captured.err
    assert SECRET_VALUE not in event.message
    assert SECRET_VALUE not in str(event.metadata)
    assert SECRET_VALUE not in captured.err


def test_backup_failure_alert_config_error_does_not_mask_backup_failure(
    backup_script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_backup(config: object) -> None:
        raise PostgresBackupError(f"pg_dump failed with {SECRET_VALUE}")

    def send_alert(config: object, event: object):
        raise external_alerts.ExternalAlertDeliveryError(
            "external alert config invalid: webhook_url is required"
        )

    monkeypatch.setenv("WEBHOOK_ALERTS_ENABLED", "true")
    monkeypatch.setattr(backup_script, "run_pg_dump_backup", fail_backup)
    monkeypatch.setattr(backup_script, "send_external_alert", send_alert)

    exit_code = backup_script.main(["--output-dir", "backups"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "PostgreSQL backup alert failed: ExternalAlertDeliveryError" in captured.err
    assert "webhook_url is required" not in captured.err
    assert SECRET_VALUE not in captured.err
