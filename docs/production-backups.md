# Production PostgreSQL Backups

Production backups are wired as an explicit one-shot Docker Compose profile. The backup job creates a plain SQL dump named `backup_YYYYMMDD.sql` in `POSTGRES_BACKUP_DIR`.

## Environment

Set a host directory in `.env.prod`:

```bash
POSTGRES_BACKUP_DIR=/srv/trading/backups
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

## Daily Scheduling

Use host cron or a systemd timer to run the one-shot job. Example cron entry for 03:15 server time:

```cron
15 3 * * * cd /srv/trading/crypto-copy-trading-platform && docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm postgres-backup >> /srv/trading/backups/backup.log 2>&1
```

Review the schedule, timezone, disk capacity, and restore process before relying on it.

## Safety Notes

- `POSTGRES_PASSWORD` is passed to `pg_dump` through `PGPASSWORD` in the container environment, not as a command argument.
- Backup files contain sensitive account, order, audit, and user data. Protect the directory and do not commit dumps to GitHub.
- Keep backups outside the application source tree in staging and production.
- Test restore drills separately before production use.
- Add retention only after confirming off-server backup copies and restore procedures.

Do not use these cleanup commands for backup management:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

These can remove data volumes, networks, cache, or evidence needed for audit and reconciliation.
