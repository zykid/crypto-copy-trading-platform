# Production Incident Response Runbook

This runbook defines conservative first-response rules for production incidents. It is intentionally focused on decision safety, audit preservation, and trading freeze controls. It does not authorize real trading or a live database restore by itself.

## Incident Priorities

Handle incidents in this order:

1. Protect funds and prevent new unintended orders.
2. Preserve audit evidence and current system state.
3. Stabilize access to read-only diagnostics.
4. Decide recovery actions with operator approval.
5. Document what happened and what changed.

Do not prioritize service uptime over funds, auditability, or data correctness.

## Severity Levels

Use these initial severity levels until a fuller incident system exists:

- `SEV1`: possible fund loss, unintended order execution, cross-tenant data exposure, leaked secret, production database corruption, or emergency stop required.
- `SEV2`: failed backups, persistent reconciliation drift, degraded order processing, repeated rate-limit blocks, or unavailable core API.
- `SEV3`: monitoring gaps, non-critical notification failure, documentation gap, or recoverable single-service restart.

When uncertain, escalate severity rather than continuing normal operation.

## Immediate Actions

For `SEV1` or any unclear trading risk:

1. Enable emergency stop through the approved backend control path once it exists for production.
2. Stop new manual trading, copy trading, strategy execution, webhook execution, and AI signal execution.
3. Keep login, read-only query, audit, and diagnostic access available when possible.
4. Do not delete containers, volumes, logs, database files, or backup files.
5. Capture timestamps, commit SHA, running containers, and affected services.

Until a production emergency stop endpoint is explicitly deployed and verified, use the most conservative available operational control for the deployment, such as disabling ingress to order execution paths or stopping execution workers while preserving database and logs.

## Evidence Preservation

Record the following before making recovery changes:

- incident start time and timezone
- operator name
- current Git commit SHA
- affected environment and host
- running Docker services and health status
- latest CI and Docker Integration status for the deployed commit
- relevant backend, proxy, PostgreSQL, Redis, and worker logs
- latest backup file name and verification status
- whether external alerts fired successfully

Do not paste secrets, API keys, database URLs, exact balances, exact positions, or user-identifying data into incident notes stored in GitHub.

## Backup And Restore Decision Gate

A live production restore requires explicit operator approval and must not be improvised from the restore drill runbook.

Before approving a production restore, confirm:

- new order execution is stopped
- affected services are stable enough for a controlled maintenance window
- the target backup file has passed `scripts/backup/verify_backup_file.py`
- the backup has been restored successfully in an isolated drill target
- the restore target and source are clearly identified
- audit logs and incident notes have been preserved
- rollback and post-restore verification steps are written down

Never restore over the production database from an unverified backup.

## Service Restart Guidance

Allowed low-risk restart actions should preserve data volumes and logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml restart backend
```

Restart one service at a time when possible and re-check health before moving on.

Do not use:

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

These commands can destroy data, caches, networks, or evidence required for reconciliation and audit.

## Communication Rules

External alerts and incident notes must stay coarse:

- say which component is affected
- include severity and current status
- include next operator action
- do not include secrets or sensitive account data
- do not include exact balances, positions, order quantities, or user identifiers

Example safe message:

```text
SEV2: PostgreSQL backup failed on production. New trading remains disabled by default. Operator review required.
```

## Recovery Verification

Before closing an incident, verify:

- health endpoints are green
- PostgreSQL and Redis are healthy
- CI and Docker Integration are green for the deployed commit
- backup job succeeds or a follow-up issue exists
- no unexpected new orders were accepted during the incident window
- audit/system event records are preserved
- notification delivery status is recorded

## Post-Incident Review

Create a private incident record outside GitHub if it contains operationally sensitive details. The record should include:

- timeline
- root cause or current hypothesis
- customer/fund impact assessment
- commands run
- files restored or changed
- alerts fired or missed
- follow-up work

Any code or documentation fixes can be committed separately after secrets and sensitive details are removed.