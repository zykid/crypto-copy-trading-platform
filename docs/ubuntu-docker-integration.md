# Ubuntu Docker Integration Guide

This guide covers the phase 2 mock-only integration environment. It is intended for an Ubuntu server accessed through Tailscale.

No real exchange trading is enabled in this phase. Do not configure real exchange API keys, do not enable TESTNET by default, and do not enable REAL trading.

## Phase Goal

Validate that the GitHub-built project runs correctly on a persistent Ubuntu Docker host with:

- Docker Compose services for PostgreSQL, Redis, backend, and frontend.
- MockExchange full-chain API execution.
- PostgreSQL and Redis health checks.
- data persistence across container restarts.
- idempotency and risk-control behavior.
- Tailscale private access.
- safe backup and restore drill preparation.

## Server Prerequisites

Install on Ubuntu:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl python3
```

Install Docker using Docker's official Ubuntu instructions, then verify:

```bash
docker --version
docker compose version
```

Install and enable Tailscale if remote private access is needed:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale status
tailscale ip -4
```

Use the Tailscale IP or MagicDNS name for private access. Do not expose the service publicly during phase 2.

## Clone Repository

```bash
sudo mkdir -p /srv/trading
sudo chown "$USER":"$USER" /srv/trading
cd /srv/trading
git clone https://github.com/zykid/crypto-copy-trading-platform.git
cd crypto-copy-trading-platform
```

Create local environment variables:

```bash
cp .env.example .env
```

Edit `.env` and use strong local values:

```bash
nano .env
```

At minimum, change:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `SECRET_ENCRYPTION_KEY`

The `DATABASE_URL` password must match `POSTGRES_PASSWORD`.

Keep these values for phase 2:

```bash
ENVIRONMENT=development
TESTNET_ADAPTERS_ENABLED=false
```

## Preflight Check

Run the repository preflight before starting containers:

```bash
python3 scripts/integration/ubuntu_preflight.py --repo-root . --env-file .env
```

Expected output includes:

```text
Ubuntu integration preflight passed
TESTNET adapters enabled: false
```

Do not continue if preflight fails.

## Start Services

```bash
docker compose up --build -d postgres redis backend frontend
```

Check status:

```bash
docker compose ps
```

Check backend logs:

```bash
docker compose logs --tail=200 backend
```

Do not continue if Alembic migration fails or backend health checks are unhealthy.

## Access Through Tailscale

From another device on the same tailnet:

- Frontend: `http://TAILSCALE_IP:3000`
- Backend health: `http://TAILSCALE_IP:8000/api/v1/health`
- Backend dependency health: `http://TAILSCALE_IP:8000/api/v1/health/dependencies`
- Backend docs: `http://TAILSCALE_IP:8000/docs`

Replace `TAILSCALE_IP` with the Ubuntu server's Tailscale IP or MagicDNS hostname.

## Run Mock Integration Checks

Run the lightweight container health check:

```bash
docker compose run --rm integration-test
```

Run the full API integration script from the host:

```bash
python3 scripts/integration/mock_compose_check.py
```

The full script validates:

- PostgreSQL and Redis health.
- register/login.
- duplicate email and username rejection.
- account persistence.
- cross-user access rejection.
- permission sharing defaults.
- API key metadata without secret disclosure.
- default risk rejection.
- idempotent execution.
- risk enablement for SIMULATION.
- Mock fill.
- position update.
- target position delta execution.

## Data Persistence Verification

Create data through the app or run the integration script, then restart services without deleting volumes:

```bash
docker compose restart postgres redis backend
```

Verify data still exists by checking PostgreSQL directly:

```bash
docker compose exec postgres psql -U trading -d trading_dev -c "select count(*) from users;"
docker compose exec postgres psql -U trading -d trading_dev -c "select count(*) from exchange_accounts;"
docker compose exec postgres psql -U trading -d trading_dev -c "select count(*) from order_executions;"
```

Redis health can be checked with:

```bash
docker compose exec redis redis-cli ping
```

Expected output:

```text
PONG
```

## Backup Smoke Test

Create a host backup directory outside the source tree:

```bash
sudo mkdir -p /srv/trading/backups
sudo chown "$USER":"$USER" /srv/trading/backups
chmod 700 /srv/trading/backups
```

Run the production-style backup profile against the mock integration database only after the core services are healthy:

```bash
POSTGRES_BACKUP_DIR=/srv/trading/backups docker compose --profile backup run --rm postgres-backup
```

If the development Compose file does not include the backup profile in your current branch, keep this step for the later production Compose validation and do not improvise destructive cleanup commands.

## Acceptance Record

Record these results before considering phase 2 complete:

- Git commit SHA deployed on the Ubuntu server.
- `python3 scripts/integration/ubuntu_preflight.py` output.
- `docker compose ps` output.
- `/api/v1/health` and `/api/v1/health/dependencies` responses.
- `docker compose run --rm integration-test` result.
- `python3 scripts/integration/mock_compose_check.py` result.
- PostgreSQL persistence counts before and after restart.
- Redis `PONG` result.
- Tailscale IP or MagicDNS name used for private access.

Do not record secrets, JWTs, API keys, order responses with sensitive IDs, or database dumps in shared tickets or GitHub.

## Safe Shutdown

Use this command to stop containers without deleting persistent data:

```bash
docker compose down --remove-orphans
```

This stops containers but keeps named volumes.

## Forbidden Commands

Do not run these commands in this project unless there is a deliberate backup and restore plan:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

These can remove data, networks, caches, and named volumes. In a trading system, accidental data loss can break audit trails, reconciliation, and incident analysis.

## Current Phase Limitations

- Real exchange trading is disabled.
- Testnet trading is not enabled by default.
- Risk settings can only be modified for `SIMULATION` accounts in V1.
- MockExchange is the only execution adapter covered by this integration guide.
- Public HTTPS, production monitoring, and alerting are documented but not required for phase 2 completion.
