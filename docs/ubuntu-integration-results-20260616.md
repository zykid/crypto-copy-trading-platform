# Ubuntu Integration Results - 2026-06-16

This record documents Phase 2 Ubuntu Docker integration validation for the mock-only environment. It intentionally excludes secrets, JWTs, API keys, raw database dumps, and sensitive trading data.

## Deployment

- Date: 2026-06-16
- Operator: zykid / Codex
- Ubuntu host: `192.168.2.42`
- Access path used for this temporary test: LAN HTTP
- Tailscale status: installed and authenticated on the host, reserved for later formal remote access validation
- Git commit SHA deployed on Ubuntu: `a28e277`
- Safety mode: `TESTNET_ADAPTERS_ENABLED=false`; no real trading enabled

## Preflight

- Command: `python3 scripts/integration/ubuntu_preflight.py --repo-root . --env-file .env`
- Result: passed
- Output summary:
  - `Ubuntu integration preflight passed`
  - `TESTNET adapters enabled: false`

## Service Health

- Command: `docker compose ps`
- Result summary:
  - `trading-dev-postgres`: running, healthy
  - `trading-dev-redis`: running, healthy
  - `trading-dev-backend`: running, healthy
  - `trading-dev-frontend`: running
- Backend health URL: `http://192.168.2.42:8000/api/v1/health`
- Dependency health URL: `http://192.168.2.42:8000/api/v1/health/dependencies`
- Health result: `status=ok`
- Dependency result: `database=ok`, `redis=ok`
- Frontend URL: `http://192.168.2.42:3000/`
- Frontend HTTP status: `200`

## Mock Integration

- Command: `docker compose run --rm integration-test`
- Result: passed
- Command: `python3 scripts/integration/mock_compose_check.py`
- Result: passed
- Host/LAN API validation result: passed against `http://192.168.2.42:8000/api/v1`

Validated behavior:

- User registration and login
- Duplicate email and duplicate username rejection
- Mock SIMULATION exchange account creation
- Tenant-isolated account reads
- Authorization sharing defaults
- API key metadata response without secret disclosure
- Default risk rejection before risk settings are enabled
- Idempotent order execution
- Cross-user execution rejection
- SIMULATION-only risk settings update
- Mock order fill to `FILLED`
- Position update after fill
- Target-position delta execution

## Persistence

Counts before restart:

- Users: `23`
- Exchange accounts: `11`
- Order executions: `33`

Restart command:

- `docker compose restart postgres redis backend`

Counts after restart and another mock integration run:

- Users: `25`
- Exchange accounts: `12`
- Order executions: `36`

Redis ping result:

- `PONG`

Conclusion: PostgreSQL named-volume persistence and Redis availability were validated without deleting volumes.

## Backup Smoke Test

- Development Compose file does not define a backup profile.
- Production Compose file defines `postgres-backup` under the `backup` profile.
- Per `docs/ubuntu-docker-integration.md`, backup smoke testing is reserved for production Compose validation when the development Compose file lacks the backup profile.
- No ad-hoc backup command was improvised during this Phase 2 mock-only validation.

## Compose Project Isolation

- Development Compose project name: `trading-dev`
- Production Compose project name: `trading-prod`
- Existing development named volumes emitted Docker label warnings from earlier project naming, but containers and volumes remained functional.
- No destructive cleanup commands were used.

## Notes

- Temporary test access used LAN HTTP endpoints as requested.
- HTTPS, reverse proxy, WAF/NPM integration, and formal Tailscale access remain later deployment validation items.
- This phase remains mock-only and simulation-only.
