# Production Readiness Checklist

This checklist tracks the remaining work before the platform can be considered a long-running production candidate. It is intentionally conservative and does not authorize REAL trading.

## Completed Baseline

- Production Compose skeleton with PostgreSQL, Redis, backend, frontend, Caddy, Prometheus, and Grafana placeholders.
- `restart: unless-stopped` and service health checks for production containers.
- Docker log rotation through bounded `json-file` settings.
- PostgreSQL backup job, backup verification helper, restore drill runbook, and systemd timer templates.
- Host systemd backup timer installation and verification runbook with a read-only timer validation script.
- Guarded Telegram, email, and webhook alert senders disabled by default.
- Safe operational alert helpers for dependency health, backup failure, emergency stop, order failure, rate-limit events, and reconciliation drift.
- Non-blocking operational alert runtime bridge for future service integrations.
- External alert smoke-test command that sends only synthetic safe operational metadata.
- Runtime rate-limit blocking can emit safe operational alerts when an alert runtime is explicitly injected.
- Emergency stop enablement through risk settings disablement emits a safe account-scope operational alert.
- Manual signal execution terminal failures emit safe order-failure operational alerts.
- Position reconciliation drift emits safe operational alerts without account, symbol, or quantity details when an alert runtime is injected.
- Dependency health monitor worker behind the `monitoring` profile and disabled by default.
- CI and Docker Integration workflows for mock full-chain validation.

## Remaining Tasks

1. Add production deployment verification steps for Caddy HTTPS certificate issuance and private access through Tailscale.
2. Add Prometheus scrape verification and starter Grafana dashboard documentation for backend health and dependency state.
3. Add backup retention guidance and a non-destructive cleanup script that never deletes active PostgreSQL volumes.
4. Add operational runbook steps for disabling TESTNET adapters and confirming `REAL` remains unavailable by default.
5. Add an explicit production preflight checklist covering secrets, API key withdrawal permissions, account mode, database backup, restore drill, monitoring, alerts, and rollback.

## Safety Notes

- Keep all external alert channels disabled until destinations are configured and tested.
- Do not send user, account, order, balance, position, signal, client order, exchange response, or API secret data through alerts.
- Do not use Docker prune commands or `docker compose down -v` for this project.
- This checklist does not enable real trading; REAL mode requires a later, separate small-funds validation phase.
