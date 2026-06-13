# Production Readiness Checklist

This checklist tracks the remaining work before the platform can be considered a long-running production candidate. It is intentionally conservative and does not authorize REAL trading.

## Completed Baseline

- Production Compose skeleton with PostgreSQL, Redis, backend, frontend, Caddy, Prometheus, and Grafana placeholders.
- `restart: unless-stopped` and service health checks for production containers.
- Docker log rotation through bounded `json-file` settings.
- PostgreSQL backup job, backup verification helper, restore drill runbook, and systemd timer templates.
- Guarded Telegram, email, and webhook alert senders disabled by default.
- Safe operational alert helpers for dependency health, backup failure, emergency stop, order failure, and rate-limit events.
- Non-blocking operational alert runtime bridge for future service integrations.
- External alert smoke-test command that sends only synthetic safe operational metadata.
- Dependency health monitor worker behind the `monitoring` profile and disabled by default.
- CI and Docker Integration workflows for mock full-chain validation.

## Remaining Tasks

1. Enable the backup systemd timer on the target Ubuntu host and verify that `backup_YYYYMMDD.sql` files are created in the intended directory.
2. Wire the operational alert runtime into real service events for emergency stop enablement, order terminal failure, runtime rate-limit blocking, and reconciliation drift.
3. Add production deployment verification steps for Caddy HTTPS certificate issuance and private access through Tailscale.
4. Add Prometheus scrape verification and starter Grafana dashboard documentation for backend health and dependency state.
5. Add backup retention guidance and a non-destructive cleanup script that never deletes active PostgreSQL volumes.
6. Add operational runbook steps for disabling TESTNET adapters and confirming `REAL` remains unavailable by default.
7. Add an explicit production preflight checklist covering secrets, API key withdrawal permissions, account mode, database backup, restore drill, monitoring, alerts, and rollback.

## Safety Notes

- Keep all external alert channels disabled until destinations are configured and tested.
- Do not send user, account, order, balance, position, signal, client order, exchange response, or API secret data through alerts.
- Do not use Docker prune commands or `docker compose down -v` for this project.
- This checklist does not enable real trading; REAL mode requires a later, separate small-funds validation phase.
