# Production Compose Skeleton

This file documents the first production runtime skeleton for the platform. It is intentionally conservative: it improves process supervision, health checks, HTTPS reverse proxy wiring, optional monitoring placeholders, safe backend metrics scraping, guarded external alert senders, PostgreSQL backup job wiring, backup failure alert wiring, disabled-by-default dependency health monitor helpers, frontend production image wiring, systemd backup timer templates, restore drill guidance, production incident response guidance, and log rotation, but it does not enable real trading.

## Files

- `docker-compose.prod.yml`
- `.env.prod.example`
- `frontend/Dockerfile`
- `frontend/next.config.mjs`
- `deploy/caddy/Caddyfile`
- `deploy/prometheus/prometheus.yml`
- `deploy/systemd/trading-postgres-backup.service`
- `deploy/systemd/trading-postgres-backup.timer`
- `scripts/backup/verify_backup_file.py`
- `docs/frontend-production-image.md`
- `docs/monitoring-placeholders.md`
- `docs/external-alert-placeholders.md`
- `docs/production-backups.md`
- `docs/production-incident-response.md`
- `docs/restore-drill-runbook.md`
- `docs/systemd-backup-timer.md`

## Runtime Properties

The production Compose file sets:

- `restart: unless-stopped` for long-running services
- health checks for PostgreSQL, Redis, and the backend API
- named production volumes for PostgreSQL, Redis, Caddy, Prometheus, and Grafana
- bounded Docker `json-file` log rotation
- required environment variables for secrets and connection strings
- Caddy reverse proxy on ports 80 and 443
- Next.js standalone frontend runtime served by `node server.js`
- optional Prometheus and Grafana services behind the `monitoring` profile
- safe backend `/metrics` scrape from inside the Compose network
- explicit PostgreSQL backup job behind the `backup` profile
- host systemd timer templates for daily PostgreSQL backups
- backup failure alerts through disabled-by-default external alert channels
- safe dependency health alert construction, throttled dispatch, and disabled monitor tick helper
- dependency health monitor environment variables that remain disabled by default
- backup file verification helper and restore drill runbook
- production incident response runbook for restore and trading-freeze decisions
- disabled-by-default Telegram, email, and webhook alert senders
- `TESTNET_ADAPTERS_ENABLED=false` by default

## HTTPS Reverse Proxy

Caddy terminates HTTPS and routes traffic inside the Compose network:

- `/api/*` -> backend
- `/docs*` -> backend
- `/redoc*` -> backend
- `/openapi.json` -> backend
- all other requests -> frontend

Before using the production proxy, point `PUBLIC_DOMAIN` DNS to the server and make sure inbound ports 80 and 443 are reachable. Caddy needs port 80 or DNS-compatible challenge support to issue certificates.

## Start Command

Create a real `.env.prod` from the example and replace every placeholder secret before starting services:

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d postgres redis backend frontend caddy
```

Check health and logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 backend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 caddy
```

Start optional monitoring placeholders:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d prometheus grafana
```

Run an explicit PostgreSQL backup:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm postgres-backup
```

Stop containers without deleting data volumes:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down --remove-orphans
```

## Safety Constraints

- Do not put real API secrets in `.env.prod.example`, README files, logs, or GitHub.
- Do not enable REAL account mode in this stage.
- Do not enable testnet trading unless that specific testnet phase is being executed manually.
- Keep withdrawal permissions disabled on exchange API keys when later testing with exchange accounts.
- Keep backup and restore drills separate from destructive Docker cleanup commands.
- Do not expose Prometheus or Grafana publicly without authentication and network controls.
- Do not send user, account, order, balance, or API secret data through external alerts.

Do not use:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

## Known Gaps

This is not yet a complete production release. Remaining production work includes:

- server-specific enablement of the backup timer on the target host
- attaching dependency health monitor ticks to a long-running loop or separate monitor process
- wiring guarded alert senders into additional operational events
