# Production PostgreSQL Backups

Production backups are wired as an explicit one-shot Docker Compose profile. The backup job creates a plain SQL dump named `backup_YYYYMMDD.sql` in `POSTGRES_BACKUP_DIR`.

## Environment

Set a host directory in `.env.prod`:

```bash
POSTGRES_BACKUP_DIR=/srv/trading/backups
POSTGRES_BACKUP_RETENTION_DAYS=30
```

Create it on the server and restrict access before running backups:

```bash
mkdir -p /srv/trading/backups
chmod 700 /srv/trading/backups
```

## Manual Backup

Run the backup job explicitly:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm postgres-backup
```

The generated file is:

```text
/srv/trading/backups/backup_YYYYMMDD.sql
```

## Failure Alerts

The backup script sends a guarded external alert only when at least one alert channel is explicitly enabled in `.env.prod`. Alerts are disabled by default.

Backup failure alerts are intentionally coarse. They include:

- severity: `critical`
- title: `PostgreSQL backup failed`
- component: `postgres_backup`
- error type

They do not include database passwords, connection strings, backup contents, user data, order data, balances, positions, or raw exception text.

Configure delivery timeout with:

```bash
ALERT_TIMEOUT_SECONDS=5
```

See `docs/external-alert-placeholders.md` for channel settings and safety rules.

## Daily Scheduling

Preferred scheduling is host systemd using the checked-in templates:

- `deploy/systemd/trading-postgres-backup.service`
- `deploy/systemd/trading-postgres-backup.timer`

See `docs/systemd-backup-timer.md` for installation and verification steps.

Example cron entry for environments that do not use systemd, scheduled for 03:15 server time:

```cron
15 3 * * * cd /srv/trading/crypto-copy-trading-platform && docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm postgres-backup >> /srv/trading/backups/backup.log 2>&1
```

Review the schedule, timezone, disk capacity, and restore process before relying on it.

## Backup Verification

Verify that a generated plain SQL backup file is readable before using it in a restore drill:

```bash
python scripts/backup/verify_backup_file.py /srv/trading/backups/backup_YYYYMMDD.sql
```

After installing the host systemd timer and running one backup, verify the timer and newest backup file together:

```bash
python scripts/backup/verify_systemd_backup_timer.py --backup-dir /srv/trading/backups
```

This check is read-only. It confirms that the timer is active, the service last completed successfully, and the latest `backup_YYYYMMDD.sql` passes the plain SQL structure checks.

For an isolated restore drill, follow `docs/restore-drill-runbook.md`. Do not restore over the production database.

## Retention Cleanup

Retention cleanup is intentionally separate from backup creation. Always inspect a dry run first:

```bash
python scripts/backup/retention_cleanup.py --backup-dir /srv/trading/backups --retention-days 30
```

Apply deletion only after confirming off-server copies, restore drills, and disk capacity:

```bash
python scripts/backup/retention_cleanup.py --backup-dir /srv/trading/backups --retention-days 30 --apply
```

The cleanup helper only considers files named `backup_YYYYMMDD.sql`. It ignores other files and directories, and it does not touch Docker volumes, containers, networks, or database files.

## Safety Notes

- `POSTGRES_PASSWORD` is passed to `pg_dump` through `PGPASSWORD` in the container environment, not as a command argument.
- Backup files contain sensitive account, order, audit, and user data. Protect the directory and do not commit dumps to GitHub.
- Keep backups outside the application source tree in staging and production.
- Test restore drills separately before production use.
- Keep at least one verified off-server copy before applying retention deletion.
- Do not use destructive Docker cleanup commands for backup management.

These can remove data volumes, networks, cache, or evidence needed for audit and reconciliation.
