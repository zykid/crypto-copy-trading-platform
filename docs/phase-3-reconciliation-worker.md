# Phase 3 Reconciliation Worker Orchestration

This note records the Phase 3 reconciliation worker boundary.

The worker is intentionally orchestration-only. It does not open real exchange connections, consume real WebSocket streams, submit orders, commit database transactions, deliver external notifications, or auto-repair positions.

## Implemented Scope

- Accepts injected exchange, database, and target position snapshot providers.
- Loads snapshots for a specific `user_id` and `exchange_account_id`.
- Runs the existing position reconciliation comparison service.
- Builds the existing audit, system-event, and notification hook plan.
- Persists audit logs, drift system events, and internal notifications through the active SQLAlchemy session.
- Keeps transaction ownership with the caller by flushing but not committing.
- Preserves `auto_fix_allowed=False`.

## Safety Boundary

- External notification channels such as Telegram, Email, and Webhook remain plan-only in this phase.
- Only internal notification plans are persisted as internal notifications.
- API keys, API secrets, passphrases, signatures, and headers are not part of worker inputs or persisted payloads.
- Snapshot providers must preserve tenant scope by loading data only for the supplied `user_id` and `exchange_account_id`.

## Validation

Covered by backend tests:

- Matched reconciliation writes an audit log only.
- Drifted reconciliation writes an audit log, a system event, and one internal notification.
- External notification channels remain excluded from internal notification persistence.
- Worker results expose the report, hook plan, and persisted records for future scheduler integration.
