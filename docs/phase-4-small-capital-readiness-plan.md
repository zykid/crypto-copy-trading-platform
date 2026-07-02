# Phase 4 Small-Capital REAL Readiness Plan

This plan defines the gate before any small-capital REAL validation. It does not authorize REAL trading.

## Entry Criteria

All items are required before any REAL trading test can be proposed:

- Dedicated test account with small isolated funds.
- Dedicated exchange API key created only for this validation.
- Withdrawal permission disabled in the exchange UI.
- API key IP restrictions configured where the exchange supports them.
- API key deleted after the validation window.
- Super admin approval recorded before the validation window.
- Emergency stop path verified before the validation window.
- Audit logging verified before the validation window.
- PostgreSQL backup and restore drill verified on an isolated target.
- Runtime health checks verified.
- Monitoring and alert placeholders reviewed.
- Account mode remains `REAL` only for the explicit test account.
- No copy trading, strategy trading, webhook trading, AI trading, or reconciliation repair executor enabled.

## Allowed First REAL Validation

The first REAL validation may only prove read-only authentication and account visibility:

- Store encrypted credentials.
- Confirm the backend never returns API secrets.
- Authenticate with the exchange using a read-only balance or account endpoint.
- Confirm account balance and position parsing.
- Confirm `trading_enabled=false`.
- Confirm risk settings `trading_enabled=false`.
- Record audit logs.
- Delete the exchange API key after the test.

No order placement is allowed in the first REAL validation.

## Later Small-Capital Order Validation

REAL order validation requires a separate approval after the read-only validation passes.

Minimum order validation controls:

- Exact symbol, side, quantity, price, and maximum notional documented before the window.
- Order window duration no longer than 10 minutes.
- Manual operator confirmation immediately before the window.
- Account trading enabled only for the approved account.
- Risk trading enabled only for the approved account.
- Kill switch verified immediately before the window.
- Runtime rate-limit enforcement active.
- Idempotent `client_order_id` required.
- Position reconciliation snapshot recorded before and after.
- API key deleted after the test.
- Post-test audit review completed.

## Hard Stop Conditions

Do not proceed if any condition is true:

- API key has withdrawal permission.
- API key is shared with another platform or production account.
- Emergency stop is unavailable.
- Backup or restore drill status is unknown.
- Audit logs are not writable.
- Account isolation cannot be verified.
- Any strategy, webhook, AI, copy trading, or repair executor is enabled.
- Operator is unsure whether the endpoint is TESTNET, demo, or REAL.

## Required Records

Every Phase 4 validation must produce a dated record containing:

- host,
- deployed commit,
- exchange,
- account mode,
- account state,
- exact allowed operation,
- safety checks,
- result,
- cleanup evidence,
- GitHub Actions status,
- Ubuntu container status.

Do not include API keys, API secrets, passphrases, JWTs, raw exchange secrets, or database dumps.

## Current Validation Records

- `docs/phase-4-real-readiness-gate-validation-20260630.md` records the first deployed readiness-gate validation on the temporary Ubuntu host. The result was `BLOCKED`, `read_only=true`, and `order_submission_authorized=false`.
- `docs/phase-4-super-admin-mfa-readiness-validation-20260630.md` records the deployed MFA readiness state. The temporary super administrator had MFA not enabled and no pending enrollment, so Phase 4 remains blocked until deliberate operator enrollment.
- `docs/phase-4-small-fund-readiness-ui-validation-20260702.md` records the deployed small-fund readiness UI panel. It consolidates required safety checks, REAL read-only status, audit trail status, and the live-order lock state for operator review before any separate small-capital order-window approval.
- `docs/phase-4-audit-log-ui-validation-20260702.md` records the deployed audit log UI and protected admin audit API validation. The frontend route loaded, the unauthenticated backend audit endpoint returned `401`, and no audit mutation or order submission was performed.
