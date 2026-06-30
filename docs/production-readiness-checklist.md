# Production Readiness Checklist

This checklist tracks the remaining work before the platform can be considered a long-running production candidate. It is intentionally conservative and does not authorize REAL trading.

## Completed Baseline

- Production Compose skeleton with PostgreSQL, Redis, backend, frontend, Caddy, Prometheus, and Grafana placeholders.
- `restart: unless-stopped` and service health checks for production containers.
- Docker log rotation through bounded `json-file` settings.
- PostgreSQL backup job, backup verification helper, restore drill runbook, and systemd timer templates.
- Host systemd backup timer installation and verification runbook with a read-only timer validation script.
- Backup retention guidance and non-destructive cleanup helper with dry-run default behavior.
- Caddy HTTPS certificate verification and private Tailscale access runbook.
- Prometheus scrape verification and starter Grafana dashboard documentation.
- TESTNET adapter disablement and REAL-unavailable safety runbook.
- Explicit production preflight checklist for secrets, account mode, backups, monitoring, alerts, and rollback.
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

No production-readiness documentation tasks remain in this checklist. This does not mean the system is approved for REAL trading.

## Next Phase Gate

Before moving beyond this GitHub and mock-integration phase, complete a separate operator review for:

- Target host provisioning and Tailscale access.
- Staging `.env.prod` values stored outside GitHub.
- Restore drill execution on an isolated database.
- TESTNET adapter enablement only in the approved testnet phase.
- REAL trading approval only in the later small-funds validation phase.
- Phase 4 small-capital validation planning in `docs/phase-4-small-capital-readiness-plan.md`.

## Safety Notes

- Keep all external alert channels disabled until destinations are configured and tested.
- Do not send user, account, order, balance, position, signal, client order, exchange response, or API secret data through alerts.
- Do not use destructive Docker cleanup commands for this project.
- This checklist does not enable real trading; REAL mode requires a later, separate small-funds validation phase.
