# Phase 3 Reconciliation Repair Planning

This note records the Phase 3 automatic reconciliation repair boundary.

The implementation is proposal-only. It is not an automatic repair executor.

## Implemented

- `build_reconciliation_repair_plan` converts a position reconciliation report into a repair plan.
- Proposal generation is disabled by default.
- Matched reconciliation reports return `NO_DRIFT`.
- Drifted reports can produce proposal-only actions when explicitly enabled:
  - `BUY_TO_TARGET`
  - `SELL_TO_TARGET`
  - `REVIEW_DATABASE_POSITION`
- Requested execution returns `EXECUTION_BLOCKED`.

## Safety Boundary

- `auto_fix_allowed` is always `False`.
- `execution_allowed` is always `False`.
- No exchange adapter is called.
- No order is submitted.
- No database position is updated.
- No transaction is committed.
- No account trading flag is changed.
- No API key, secret, passphrase, signature, request header, or exchange response is included in proposals.

## Future Work

Any real automatic repair executor must be added in a later phase with separate approval, dedicated risk checks, idempotency checks, audit records, kill-switch enforcement, rate-limit enforcement, and testnet-only validation before any REAL-mode consideration.
