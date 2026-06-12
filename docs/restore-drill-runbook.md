# Restore Drill Runbook

This runbook describes a conservative PostgreSQL restore drill for staging or an isolated test host. It is not a production restore procedure for a live trading system.

## Goals

- Verify a generated `backup_YYYYMMDD.sql` file is readable and resembles a PostgreSQL plain SQL dump.
- Restore into an isolated database target, never over the live production database.
- Confirm basic application tables exist after restore.
- Preserve auditability by keeping command output and timestamps.

## Preconditions

- Use an isolated host, staging server, or throwaway PostgreSQL container.
- Keep `TESTNET_ADAPTERS_ENABLED=false` unless a separately approved testnet phase is running.
- Do not use live exchange API keys for restore drills.
- Do not run destructive Docker cleanup commands.

## Step 1: Verify Backup File Shape

Run the repository verification helper against a backup file:

```bash
python scripts/backup/verify_backup_file.py /srv/trading/backups/backup_YYYYMMDD.sql
```

This check is intentionally non-destructive. It confirms the file is non-empty, has a PostgreSQL dump header, and includes schema/data statements.

## Step 2: Create an Isolated Restore Target

Example using a temporary PostgreSQL container with a separate named volume:

```bash
docker volume create trading-restore-drill-postgres-data
docker run --rm --name trading-restore-drill-postgres \
  -e POSTGRES_DB=trading_restore_drill \
  -e POSTGRES_USER=trading_restore \
  -e POSTGRES_PASSWORD=replace-with-drill-password \
  -v trading-restore-drill-postgres-data:/var/lib/postgresql/data \
  -p 55432:5432 \
  postgres:16-alpine
```

Run that container in a dedicated terminal. Do not reuse the production database or production volume.

## Step 3: Restore Backup Into The Drill Database

From another terminal:

```bash
PGPASSWORD=replace-with-drill-password psql \
  --host localhost \
  --port 55432 \
  --username trading_restore \
  --dbname trading_restore_drill \
  --file /srv/trading/backups/backup_YYYYMMDD.sql
```

## Step 4: Verify Restored Tables

Check expected core tables without printing sensitive rows:

```bash
PGPASSWORD=replace-with-drill-password psql \
  --host localhost \
  --port 55432 \
  --username trading_restore \
  --dbname trading_restore_drill \
  --command "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
```

Expected tables include users, exchange accounts, positions, order executions, audit logs, and system events. Do not dump row contents during routine drills.

## Step 5: Record Drill Result

Record:

- backup file name
- backup file size
- restore start and finish time
- table verification result
- any errors encountered
- operator name

Store the drill record outside GitHub if it contains hostnames, paths, usernames, or operational details.

## Cleanup

Stop the temporary restore container from its terminal with `Ctrl+C`. Remove the drill volume only after verifying you are targeting the drill volume name, not a production volume:

```bash
docker volume rm trading-restore-drill-postgres-data
```

Do not use:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

## Escalation Guidance

If a production restore is ever required, pause new trading first, preserve audit logs, notify operators, and perform restore from an approved incident plan. Do not improvise a live restore from this drill runbook.
