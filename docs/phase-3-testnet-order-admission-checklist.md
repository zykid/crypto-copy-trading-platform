# Phase 3 TESTNET Order Admission Checklist

This checklist is a gate for a later TESTNET order validation window.

It does not authorize TESTNET order submission by itself. Operators must receive a separate explicit approval before enabling any order path.

REAL order execution remains prohibited.

## Scope

This checklist applies only to controlled TESTNET or exchange demo order validation.

Allowed after separate approval:

- One dedicated test account.
- One exchange account record in `TESTNET` mode.
- One small testnet order at a time.
- Manual signal source only.
- Mock or testnet exchange endpoints only.

Prohibited:

- REAL orders.
- Copy trading orders.
- Strategy, webhook, or AI-generated orders.
- Automatic reconciliation repair execution.
- Production funds or production API keys.
- Withdrawal permission on any API key.

## Required Green Checks

Before any TESTNET order window:

1. Confirm the deployed commit matches the intended GitHub commit.
2. Confirm `CI` is green for that commit.
3. Confirm `Docker Integration` is green for that commit.
4. Confirm the Ubuntu deployment is healthy.
5. Confirm frontend and backend are reachable on the approved test network.
6. Confirm the database backup path is configured and writable.
7. Confirm audit logs and system events can be written.
8. Confirm `GET /api/v1/orders/testnet/admission-check` returns only read-only status data.

## Required Account State

The target exchange account must satisfy all conditions:

- `mode = TESTNET`.
- `trading_enabled = false` before the approved test window.
- Credentials are encrypted and never returned to the frontend.
- API key is dedicated to this test.
- API key is testnet/demo only.
- Withdrawal permission is disabled where the exchange supports it.
- IP restriction is enabled where the exchange supports it.
- Account belongs to the logged-in user or is accessed through explicit authorization.

## Required Runtime Gates

These gates must be verified before the temporary order window:

- `TESTNET_ADAPTERS_ENABLED=false` before preparation starts.
- Emergency stop is available and not stale.
- Global kill switch behavior has been tested recently.
- Exchange account `trading_enabled=false`.
- Risk setting `trading_enabled=false`.
- Copy trading, strategy trading, webhook trading, and AI trading remain disabled.
- Reconciliation repair execution remains disabled.
- The read-only admission check returns `order_submission_authorized=false`.

During the approved test window only:

- `TESTNET_ADAPTERS_ENABLED=true` may be set temporarily.
- Exchange account `trading_enabled=true` may be set temporarily.
- Risk setting `trading_enabled=true` may be set temporarily.
- A per-account testnet order enable confirmation must be written to audit logs.

After the window:

- Set `TESTNET_ADAPTERS_ENABLED=false`.
- Set exchange account `trading_enabled=false`.
- Set risk setting `trading_enabled=false`.
- Confirm no follow-up worker can submit another order.

## Required Risk Limits

Configure conservative limits before enabling order submission:

- Symbol allowlist contains only the test symbol.
- Single-order notional cap is minimal.
- Maximum position cap is minimal.
- Maximum leverage is disabled or set to the minimum practical value.
- Minimum and maximum quantity rules are loaded from the exchange symbol metadata.
- Runtime rate-limit checks are enabled.
- Daily loss limit remains reserved; do not use it as the only protection.

If any limit cannot be confirmed, do not start the order window.

## Required Order Controls

Every TESTNET order request must include or enforce:

- `signal_id`.
- `execution_id`.
- `client_order_id`.
- Idempotency on `signal_id + exchange_account_id`.
- Account mode check equals `TESTNET`.
- Adapter gate check.
- Risk passed state before submission.
- Order state machine tracking from `CREATED`.
- Audit log entry before and after exchange submission attempt.

The order must not be sent if any required identifier is missing.

## Required Observation

During the test:

- Watch the order execution response.
- Watch order state changes.
- Watch balances and positions.
- Watch runtime rate-limit counters.
- Watch audit logs.
- Watch system events and internal notifications.

After the test:

- Run position reconciliation.
- Confirm database position, exchange position, and target position are consistent or record the drift.
- Do not auto-repair drift.
- Record any drift as an observation.

## Hard Stop Conditions

Immediately stop the test and revert all temporary flags if any condition occurs:

- Any request targets a REAL endpoint.
- Any order uses a non-test account.
- Any API key has withdrawal permission.
- Any secret appears in frontend output, logs, screenshots, or docs.
- Any duplicate order is attempted for the same `signal_id + exchange_account_id`.
- Runtime rate-limit service blocks the request.
- Risk engine rejects the request.
- Order state becomes `FAILED`, `REJECTED`, `TIMEOUT`, or unknown.
- Reconciliation reports unexpected drift.
- Emergency stop does not block new order requests.

## Required Cleanup

After the test window:

1. Disable testnet adapters.
2. Disable exchange account trading.
3. Disable risk setting trading.
4. Confirm copy trading and strategy paths remain disabled.
5. Delete or deactivate the temporary exchange API key when the test is complete.
6. Remove or deactivate the temporary platform credential if it is no longer needed.
7. Run reconciliation in report-only mode.
8. Record the result in a dated validation document based on `docs/phase-3-testnet-order-validation-template.md`.
9. Confirm `CI` and `Docker Integration` remain green after any follow-up changes.

## Acceptance Criteria

The TESTNET order stage can be considered ready only when:

- All preconditions above are checked.
- The operator has separate explicit approval for the order window.
- All temporary flags have an owner and rollback time.
- Emergency stop is verified before order submission.
- The order path remains unavailable for REAL accounts.
- The order path remains unavailable for copy trading, strategy, webhook, and AI sources.
- Cleanup and result recording are completed.
