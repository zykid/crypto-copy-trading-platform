# PostgreSQL Backups

This project keeps PostgreSQL backup support explicit and conservative. Backup outputs are plain SQL dumps named `backup_YYYYMMDD.sql`, and the database password is not placed in `pg_dump` command arguments.

## Local or Server Script Usage

Set the PostgreSQL variables in `.env` or the process environment:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_dev
POSTGRES_USER=trading
POSTGRES_PASSWORD=change-me
POSTGRES_BACKUP_DIR=backups
```

Run the backup script from the repository root:

```bash
python scripts/backup/postgres_backup.py
```

The output path defaults to:

```text
backups/backup_YYYYMMDD.sql
```

You can override the output directory:

```bash
python scripts/backup/postgres_backup.py --output-dir /srv/trading/backups
```

## Production Compose Job

Production also has an explicit one-shot Compose backup profile:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm postgres-backup
```

See `docs/production-backups.md` for server directory permissions, cron scheduling, and restore guidance.

## Safety Notes

- The Python script uses `PGPASSWORD` in the child process environment so the password is not included in the command line.
- The production Compose job also maps `POSTGRES_PASSWORD` into `PGPASSWORD` inside the backup container.
- The generated dump uses `--format plain`, `--no-owner`, and `--no-privileges` for portability across staging and production restore targets.
- Keep backup files outside the application source tree in staging and production.
- Protect backup directories with filesystem permissions and server backups.
- Do not commit generated `.sql` backup files to GitHub.

## Forbidden Cleanup Commands

Do not run these commands as part of backup or restore workflows:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

These commands can remove data, Docker volumes, networks, or evidence needed for audit and reconciliation.
