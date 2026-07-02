# Phase 4 Small-Capital Final Checklist

This checklist is the final gate before any small-capital REAL validation.

It does not authorize REAL order placement by itself. REAL order placement requires
a separate explicit approval after the REAL read-only validation passes.

## Scope

This checklist applies only to dedicated test accounts with isolated small funds.

Allowed for the first Phase 4 validation:

- One dedicated exchange account.
- One dedicated platform exchange account record.
- `REAL` mode for the explicit test account only.
- Read-only exchange authentication.
- Balance and position visibility checks.
- Audit, system event, and safety-state verification.

Prohibited during the first Phase 4 validation:

- REAL order placement.
- Copy trading.
- Strategy trading.
- Webhook trading.
- AI-generated trading.
- Automatic reconciliation repair execution.
- Shared exchange API keys.
- API keys with withdrawal permission.
- Production or personal main-account funds.

## Required Green Checks

Before any REAL read-only validation:

1. Confirm the deployed commit matches the intended GitHub commit.
2. Confirm `CI` is green for that commit.
3. Confirm `Docker Integration` is green for that commit.
4. Confirm the Ubuntu deployment is healthy.
5. Confirm frontend and backend are reachable only on the approved test network.
6. Confirm PostgreSQL backup and isolated restore drill are verified.
7. Confirm the configured storage path is writable and outside the source tree.
8. Confirm audit logs are writable.
9. Confirm system events are writable.
10. Confirm secrets never appear in frontend responses, screenshots, logs, or docs.

## Required Operator Checks

The operator must confirm all items before starting:

- The exchange account is a dedicated test account.
- The account contains only isolated small funds or no funds for read-only testing.
- The API key was created specifically for this validation.
- Withdrawal permission is disabled.
- IP restrictions are configured where the exchange supports them.
- The exchange endpoint is known and documented as REAL, not TESTNET or demo.
- The API key will be deleted after the validation window.
- No other trading platform is using the same API key.
- The validation window has a start time, end time, and named operator.

If any item is uncertain, stop and do not continue.

## Required Platform State

Before REAL read-only validation:

- `TESTNET_ADAPTERS_ENABLED=false` unless a separate TESTNET window is running.
- The selected exchange account has `mode = REAL`.
- The selected exchange account has `trading_enabled = false`.
- Risk settings for the account have `trading_enabled = false`.
- Global emergency stop path is available.
- Copy trading rules are disabled or not attached to the account.
- Strategy, webhook, and AI signal sources are disabled.
- Reconciliation repair execution is disabled.
- Rate-limit service is active.
- The UI clearly shows no live order is authorized.

## Required Credential Handling

Credential handling must satisfy all conditions:

- API key secret and passphrase are encrypted at rest.
- API secret and passphrase are never returned to the frontend.
- API secret and passphrase are never written to logs.
- API secret and passphrase are never committed to GitHub.
- Credential save requires current-login password or an equivalent reauthentication
  mechanism.
- Read-only authentication result records only metadata, not secrets.

## First REAL Validation: Read-Only Only

The first REAL validation may perform only these actions:

1. Store encrypted API credentials.
2. Confirm credential status without returning secrets.
3. Run read-only exchange authentication.
4. Fetch balances.
5. Fetch positions.
6. Confirm `trading_enabled=false`.
7. Confirm risk `trading_enabled=false`.
8. Confirm no order submission endpoint is authorized.
9. Record audit logs and system events.
10. Delete the API key after the validation is complete.

The first REAL validation passes only if all of these are true:

- Exchange authentication succeeds.
- Balance and position parsing succeeds.
- No secret is exposed.
- No order is submitted.
- Audit records are present.
- The API key is deleted after the test.

## Later Small-Capital Order Window

REAL order validation is a separate later step.

Before a REAL order window, create a dated order-window record with:

- exact exchange,
- account ID,
- symbol,
- side,
- order type,
- quantity,
- price or price guard,
- maximum notional,
- allowed start time,
- allowed end time,
- rollback owner,
- emergency stop operator,
- post-test cleanup owner.

The order window must be no longer than 10 minutes.

During the approved order window only:

- Account trading may be enabled for the approved account only.
- Risk trading may be enabled for the approved account only.
- A single approved order may be submitted.
- The order must include `signal_id`, `execution_id`, and `client_order_id`.
- Idempotency on `signal_id + exchange_account_id` must be enforced.

After the order window:

- Disable account trading.
- Disable risk trading.
- Confirm no worker can submit follow-up orders.
- Run reconciliation in report-only mode.
- Record order state transitions.
- Delete the API key when the test is complete.

## Hard Stop Conditions

Stop immediately if any condition is true:

- The API key has withdrawal permission.
- The API key is shared or reused from another system.
- The selected account is not the dedicated test account.
- The UI or API cannot confirm `trading_enabled=false` before read-only validation.
- Emergency stop is unavailable or stale.
- Backup or restore drill status is unknown.
- Audit logs are not writable.
- Any secret appears in frontend output, logs, screenshots, or docs.
- Any copy trading, strategy, webhook, AI, or repair executor path is enabled.
- Operator is unsure whether the endpoint is TESTNET, demo, or REAL.
- Any unexpected order submission attempt occurs.

## Required Evidence

Each Phase 4 validation record must include:

- host,
- deployed commit,
- GitHub Actions status,
- Ubuntu container status,
- exchange,
- account mode,
- account state,
- allowed operation,
- safety checks,
- read-only authentication result,
- audit/system event result,
- cleanup evidence,
- final result.

Do not include:

- API keys,
- API secrets,
- passphrases,
- JWTs,
- database passwords,
- raw database dumps,
- raw exchange secret payloads.

## Acceptance Criteria

The platform can proceed to a first REAL read-only validation only when:

- Every required green check is satisfied.
- Every required operator check is confirmed.
- Required platform state is confirmed.
- Credential handling is verified.
- Hard stop conditions are all false.
- A dated validation record is prepared.

The platform can proceed to a REAL small-capital order window only after:

- The REAL read-only validation passes.
- The API key from the read-only validation is deleted or explicitly rotated.
- A separate order-window approval is recorded.
- The order-window plan passes review.
- Emergency stop is verified immediately before the window.
