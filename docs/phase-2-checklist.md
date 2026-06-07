# Phase 2 Checklist

Phase 2 target: Ubuntu Server Docker integration tests with PostgreSQL, Redis, and full MockExchange execution path.

## Completed

- Docker Compose service definitions
- PostgreSQL container with named volume
- Redis container with named volume
- Backend container health check
- Frontend container build
- Alembic migration on backend startup
- GitHub Docker Integration workflow
- Backend dependency health endpoint
- PostgreSQL connectivity check
- Redis connectivity check
- Mock API integration script
- User registration/login integration check
- Duplicate email and username checks
- Tenant-isolated account reads
- Authorization sharing default checks
- API key metadata without secret disclosure
- Default risk rejection check
- Idempotent order execution check
- Tenant isolation before idempotency check
- Controlled SIMULATION-only risk settings API
- Mock fill to `FILLED`
- Position update after fill
- Target-position delta execution
- Ubuntu/Tailscale integration guide
- Forbidden Docker command documentation

## Still Reserved For Later Phases

- Binance Testnet adapter
- Bybit Testnet adapter
- OKX Demo Trading adapter
- WebSocket order updates
- WebSocket balances and positions
- Rate Limit Service
- Audit Service append-only enforcement
- Position Reconciliation Service
- Notification Service
- PostgreSQL daily backup automation
- Production reverse proxy
- HTTPS
- Monitoring and alerting
- Log rotation

## Required Validation Before Closing Phase 2

Run both GitHub workflows on the latest commit:

- CI
- Docker Integration

Both must be green before moving to exchange testnet work.

## Safety Gate

Phase 3 must keep default account mode as `SIMULATION`.

TESTNET must require explicit manual account-level configuration.

REAL trading remains prohibited until the dedicated small-capital real-test phase.
