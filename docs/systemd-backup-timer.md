# Systemd Backup Timer

The repository includes host-level systemd templates for scheduling the production PostgreSQL backup job.

## Files

- `deploy/systemd/trading-postgres-backup.service`
- `deploy/systemd/trading-postgres-backup.timer`
- `scripts/backup/verify_systemd_backup_timer.py`

The service runs the existing one-shot Docker Compose backup profile and writes `backup_YYYYMMDD.sql` into `POSTGRES_BACKUP_DIR` from `.env.prod`.

## Expected Server Paths

The templates assume the repository is deployed here:

```text
/srv/trading/crypto-copy-trading-platform
```

If the production checkout uses a different path, update `WorkingDirectory` in `trading-postgres-backup.service` before installing it.

## Install

Copy the unit files on the Ubuntu server:

```bash
sudo cp deploy/systemd/trading-postgres-backup.service /etc/systemd/system/trading-postgres-backup.service
sudo cp deploy/systemd/trading-postgres-backup.timer /etc/systemd/system/trading-postgres-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now trading-postgres-backup.timer
```

Check the timer:

```bash
systemctl list-timers trading-postgres-backup.timer
systemctl status trading-postgres-backup.timer
```

Run one backup manually through systemd:

```bash
sudo systemctl start trading-postgres-backup.service
journalctl -u trading-postgres-backup.service -n 100 --no-pager
```

## Verification

After installing the timer and running one manual backup, verify the host state from the repository checkout:

```bash
python scripts/backup/verify_systemd_backup_timer.py --backup-dir /srv/trading/backups
```

The verification command checks all of the following without deleting or modifying data:

- `trading-postgres-backup.timer` is loaded and active.
- `trading-postgres-backup.service` is loaded and its last result is successful.
- `POSTGRES_BACKUP_DIR` contains at least one `backup_YYYYMMDD.sql` file.
- The newest backup file is non-empty and looks like a plain PostgreSQL SQL dump.

A passing result prints the timer unit, service result, latest backup path, and backup size. It does not print database contents, connection strings, user data, account data, orders, positions, balances, or API secrets.

If the repository or backup directory uses a custom path, pass the real backup directory:

```bash
python scripts/backup/verify_systemd_backup_timer.py --backup-dir /custom/private/backups
```

Use custom unit names only if the templates were intentionally renamed:

```bash
python scripts/backup/verify_systemd_backup_timer.py \
  --backup-dir /srv/trading/backups \
  --timer-unit trading-postgres-backup.timer \
  --service-unit trading-postgres-backup.service
```

## Acceptance Criteria

Treat the host timer as ready only when all checks pass:

1. `systemctl list-timers trading-postgres-backup.timer` shows the next scheduled run.
2. `sudo systemctl start trading-postgres-backup.service` exits successfully.
3. `journalctl -u trading-postgres-backup.service -n 100 --no-pager` shows no backup failure.
4. `scripts/backup/verify_systemd_backup_timer.py` passes against the configured backup directory.
5. The generated backup file is stored outside the application source tree and protected with restrictive permissions.

## Safety Notes

- Keep real secrets only in `.env.prod` on the server, never in systemd unit files.
- Protect `POSTGRES_BACKUP_DIR` with restrictive permissions such as `chmod 700`.
- Backup files contain sensitive user, order, audit, and account data.
- Confirm the server timezone before relying on the 03:15 schedule.
- Perform restore drills before treating backups as production-ready.

Do not use these commands for backup management:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```
