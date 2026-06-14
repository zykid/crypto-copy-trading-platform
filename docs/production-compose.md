# Production Compose Skeleton

This file documents the first production runtime skeleton for the platform. It is intentionally conservative: it improves process supervision, health checks, HTTPS reverse proxy wiring, optional monitoring placeholders, safe backend metrics scraping, guarded external alert senders, safe operational alert helpers, PostgreSQL backup job wiring, backup failure alert wiring, disabled-by-default dependency health monitor helpers, frontend production image wiring, systemd backup timer templates, restore drill guidance, production incident response guidance, backup retention guidance, Compose project isolation, and log rotation, but it does not enable real trading.

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
- `scripts/backup/verify_systemd_backup_timer.py`
- `scripts/backup/retention_cleanup.py`
- `docs/caddy-tailscale-verification.md`
- `docs/frontend-production-image.md`
- `docs/monitoring-placeholders.md`
- `docs/prometheus-grafana-verification.md`
- `docs/external-alert-placeholders.md`
- `docs/production-backups.md`
- `docs/production-incident-response.md`
- `docs/production-preflight-checklist.md`
- `docs/production-readiness-checklist.md`
- `docs/restore-drill-runbook.md`
- `docs/systemd-backup-timer.md`
- `docs/testnet-real-mode-runbook.md`

## Runtime Properties

The production Compose file sets:

- explicit Compose project name `trading-prod`
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
- runnable dependency health monitor worker service behind the `monitoring` profile
- safe emergency stop, order failure, and rate-limit alert construction with throttled dispatch helpers
- non-blocking operational alert runtime bridge for future trading-service integration points
- backup file verification helper, systemd timer verification helper, retention dry-run helper, and restore drill runbook
- production incident response runbook for restore and trading-freeze decisions
- disabled-by-default Telegram, email, and webhook alert senders
- `TESTNET_ADAPTERS_ENABLED=false` by default

## Compose Project Isolation

`docker-compose.prod.yml` declares `name: trading-prod`. The development Compose file declares `name: trading-dev`. Keep these names in place so production-like tests, production deployments, and development containers are managed as separate Compose projects even when commands are run from the same repository directory.

When running recovery drills on a shared Ubuntu test host, start and stop the production stack with `docker-compose.prod.yml` only. Do not use development Compose commands to manage production containers, and do not use production Compose commands to manage development containers.

## HTTPS Reverse Proxy

Caddy terminates HTTPS and routes traffic inside the Compose network:

- `/api/*` -> backend
- `/docs*` -> backend
- `/redoc*` -> backend
- `/openapi.json` -> backend
- all other requests -> frontend

Before using the production proxy, point `PUBLIC_DOMAIN` DNS to the server and make sure inbound ports 80 and 443 are reachable. Caddy needs port 80 or DNS-compatible challenge support to issue certificates.

Follow `docs/caddy-tailscale-verification.md` to verify HTTPS issuance and private Tailscale access.

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

Start optional monitoring placeholders and the dependency health monitor service:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d prometheus grafana dependency-health-monitor
```

The dependency health monitor starts safely with `DEPENDENCY_HEALTH_MONITOR_ENABLED=false`. Set it to `true` only after configuring at least one external alert channel and confirming that the alert destination does not expose user, order, balance, position, or API secret data.

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
- Keep development and production Compose project names isolated.
- Review backup retention dry-run output before applying deletion of old backup files.
- Do not expose Prometheus or Grafana publicly without authentication and network controls.
- Do not send user, account, order, balance, or API secret data through external alerts.

## Known Gaps

This is not yet a complete production release. Remaining production work includes server-specific execution of the preflight checklist and separate approval for later TESTNET or REAL phases.
