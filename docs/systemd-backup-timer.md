# Systemd Backup Timer

The repository includes host-level systemd templates for scheduling the production PostgreSQL backup job.

## Files

- `deploy/systemd/trading-postgres-backup.service`
- `deploy/systemd/trading-postgres-backup.timer`

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
