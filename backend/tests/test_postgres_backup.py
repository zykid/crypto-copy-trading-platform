from datetime import date
from subprocess import CompletedProcess

import pytest

from app.services.postgres_backup import (
    PostgresBackupConfig,
    PostgresBackupError,
    plan_pg_dump_backup,
    run_pg_dump_backup,
)


def make_config(tmp_path) -> PostgresBackupConfig:
    return PostgresBackupConfig(
        host="postgres",
        port=5432,
        database="trading_dev",
        username="trading",
        password="super-secret-password",
        output_dir=tmp_path,
    )


def test_plan_pg_dump_backup_uses_expected_filename_and_plain_format(tmp_path) -> None:
    config = make_config(tmp_path)

    plan = plan_pg_dump_backup(config, backup_date=date(2026, 6, 12))

    assert plan.output_path == tmp_path / "backup_20260612.sql"
    assert "--format" in plan.command
    assert "plain" in plan.command
    assert "--no-owner" in plan.command
    assert "--no-privileges" in plan.command


def test_plan_pg_dump_backup_keeps_password_out_of_command(tmp_path) -> None:
    config = make_config(tmp_path)

    plan = plan_pg_dump_backup(config, backup_date=date(2026, 6, 12))

    assert config.password not in plan.command
    assert plan.env == {"PGPASSWORD": config.password}


def test_run_pg_dump_backup_uses_safe_environment(tmp_path) -> None:
    config = make_config(tmp_path)
    calls = []

    def fake_runner(command, *, env, check, capture_output, text):
        calls.append(
            {
                "command": command,
                "env": env,
                "check": check,
                "capture_output": capture_output,
                "text": text,
            }
        )
        return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    output_path = run_pg_dump_backup(
        config,
        backup_date=date(2026, 6, 12),
        runner=fake_runner,
    )

    assert output_path == tmp_path / "backup_20260612.sql"
    assert calls[0]["env"]["PGPASSWORD"] == config.password
    assert config.password not in calls[0]["command"]
    assert calls[0]["check"] is False
    assert calls[0]["capture_output"] is True
    assert calls[0]["text"] is True


def test_run_pg_dump_backup_redacts_password_from_errors(tmp_path) -> None:
    config = make_config(tmp_path)

    def failing_runner(command, *, env, check, capture_output, text):
        return CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=f"authentication failed for {config.password}",
        )

    with pytest.raises(PostgresBackupError) as exc_info:
        run_pg_dump_backup(
            config,
            backup_date=date(2026, 6, 12),
            runner=failing_runner,
        )

    assert config.password not in str(exc_info.value)
    assert "***" in str(exc_info.value)


def test_plan_pg_dump_backup_rejects_missing_values(tmp_path) -> None:
    config = PostgresBackupConfig(
        host="",
        port=5432,
        database="trading_dev",
        username="trading",
        password="secret",
        output_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="host"):
        plan_pg_dump_backup(config)
