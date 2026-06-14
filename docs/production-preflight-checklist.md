# Production Preflight Checklist

Use this checklist before any long-running production deployment. It is a gate, not an approval to enable REAL trading.

## Secrets

- `.env.prod` exists only on the target server.
- `JWT_SECRET_KEY` is long, random, and not reused.
- `SECRET_ENCRYPTION_KEY` is generated securely and not stored in GitHub.
- PostgreSQL, Grafana, SMTP, webhook, and Telegram secrets are not committed or printed in logs.
- Exchange API secrets are encrypted at rest and never returned to the frontend.

## Account and Trading Mode

- `TESTNET_ADAPTERS_ENABLED=false` unless a reviewed TESTNET phase is active.
- REAL order execution remains unavailable by default.
- Emergency stop behavior has been tested in a non-real environment.
- Risk settings start with trading disabled until an operator explicitly enables the correct account mode.
- Exchange API keys have withdrawal permission disabled in the exchange UI.

## Database and Backups

- PostgreSQL volume is persistent and mounted only through approved Compose configuration.
- Manual backup has completed successfully.
- Systemd backup timer is installed and active on the target host.
- `verify_systemd_backup_timer.py` passes against the backup directory.
- A restore drill has been completed in an isolated environment.
- Backup retention dry-run has been reviewed before any deletion is applied.

## Networking

- Caddy obtains a valid HTTPS certificate for `PUBLIC_DOMAIN`.
- HSTS and basic security headers are present.
- Tailscale access is available for private operations.
- Prometheus and Grafana are not exposed publicly without authentication and network controls.

## Monitoring and Alerts

- Prometheus backend target is up.
- Grafana dashboard contains only safe aggregate operational panels.
- External alert channels are disabled until destinations are reviewed.
- Alert smoke tests use synthetic metadata only.
- Dependency, backup, rate-limit, emergency stop, order failure, and reconciliation drift alerts avoid sensitive data.

## Rollback

- Previous image or commit SHA is recorded before deployment.
- Database backup is completed before deployment.
- Rollback does not use destructive Docker cleanup commands.
- Incident response runbook is available to operators.

## Final Gate

Do not proceed if any item above is unresolved. Do not enable REAL trading from this checklist.
