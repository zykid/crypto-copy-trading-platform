# Production Compose Skeleton

This file documents the first production runtime skeleton for the platform. It is intentionally conservative: it improves process supervision, health checks, and log rotation, but it does not enable real trading.

## Files

- `docker-compose.prod.yml`
- `.env.prod.example`

## Runtime Properties

The production Compose file sets:

- `restart: unless-stopped` for long-running services
- health checks for PostgreSQL, Redis, and the backend API
- named production volumes: `trading-prod-postgres-data` and `trading-prod-redis-data`
- bounded Docker `json-file` log rotation
- required environment variables for secrets and connection strings
- `TESTNET_ADAPTERS_ENABLED=false` by default

## Start Command

Create a real `.env.prod` from the example and replace every placeholder secret before starting services:

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d postgres redis backend frontend
```

Check health and logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 backend
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
- HTTPS reverse proxy with Caddy or Nginx
- scheduled PostgreSQL backup container or host cron
- Prometheus and Grafana placeholders
- Telegram, email, and webhook alert senders
- restore drills and operational runbooks
