# Production Compose Skeleton

This file documents the first production runtime skeleton for the platform. It is intentionally conservative: it improves process supervision, health checks, HTTPS reverse proxy wiring, optional monitoring placeholders, and log rotation, but it does not enable real trading.

## Files

- `docker-compose.prod.yml`
- `.env.prod.example`
- `deploy/caddy/Caddyfile`
- `deploy/prometheus/prometheus.yml`
- `docs/monitoring-placeholders.md`

## Runtime Properties

The production Compose file sets:

- `restart: unless-stopped` for long-running services
- health checks for PostgreSQL, Redis, and the backend API
- named production volumes for PostgreSQL, Redis, Caddy, Prometheus, and Grafana
- bounded Docker `json-file` log rotation
- required environment variables for secrets and connection strings
- Caddy reverse proxy on ports 80 and 443
- optional Prometheus and Grafana services behind the `monitoring` profile
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

Do not use:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

## Known Gaps

This is not yet a complete production release. Remaining production work includes:

- hardened frontend production image
- scheduled PostgreSQL backup container or host cron
- reviewed backend metrics endpoint
- Telegram, email, and webhook alert senders
- restore drills and operational runbooks
