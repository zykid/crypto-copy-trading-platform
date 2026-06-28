# Phase 3 Read-Only Operator Runbook

This runbook defines what operators may test during the current Phase 3 read-only validation stage.

It does not authorize TESTNET order submission or REAL trading.

## Current Ubuntu Test Host

- Frontend: `http://192.168.2.42:3000`
- Backend API prefix: `http://192.168.2.42:8000/api/v1`
- Host purpose: temporary Ubuntu integration server.
- Intended access during temporary testing: LAN HTTP only, unless a separate reverse-proxy test is explicitly approved.

## Allowed Actions

Operators may perform these actions:

1. Health check.
2. Register or log in to test users.
3. Log in as the temporary `platform_super_admin` test account.
4. Create SIMULATION, TESTNET, or REAL account records with `trading_enabled=false`.
5. Store temporary API credentials through the encrypted credential flow.
6. Run authenticated read-only credential checks for balances and positions.
7. Confirm that encrypted credential status is displayed without returning API secret material.
8. Confirm audit/log entries contain no API keys, API secrets, passphrases, or signatures.
9. Delete the exchange-side temporary API key after the validation.
10. Deactivate or remove the temporary platform exchange account after the validation.

## Prohibited Actions

Do not perform these actions in this stage:

1. Do not enable REAL trading.
2. Do not submit REAL orders.
3. Do not submit TESTNET orders unless a separate testnet order phase is explicitly approved.
4. Do not enable copy trading, strategy trading, webhook trading, or AI signal execution.
5. Do not enable automatic reconciliation repair execution.
6. Do not grant withdrawal permission to any exchange API key.
7. Do not paste API secrets into GitHub, docs, screenshots, logs, chat, or issue text.
8. Do not use production funds for this phase.
9. Do not use destructive Docker cleanup commands.

## Required API Key Settings

For every temporary exchange API credential:

- Use a dedicated test credential.
- Disable withdrawal permission.
- Prefer read-only permission for read-only validation.
- If an exchange requires trade permission to create a key for testing, keep the platform account `trading_enabled=false`.
- Apply IP restrictions when the exchange supports them.
- Delete the key after the test.

## TESTNET Read-Only Checks

TESTNET read-only checks require all of the following:

- Account mode is `TESTNET`.
- Account belongs to the logged-in user.
- `trading_enabled=false`.
- Credentials are encrypted in the backend and never returned to the frontend.
- The request is a balance or position read-only request.

The test must fail closed if credentials are missing, invalid, region-mismatched, or exchange endpoint mode is wrong.

## REAL Read-Only Checks

REAL read-only checks are permitted only for empty or dedicated test accounts and only when:

- The exchange account is dedicated to this validation.
- Withdrawal permission is disabled.
- Platform `trading_enabled=false`.
- No order endpoint is called.
- Returned data is bounded to authentication status and balance/position metadata.
- The exchange API key is deleted after the test.

The OKX production read-only validation on 2026-06-23 is recorded in `docs/phase-3-read-only-validation-20260623.md`.

## Manual Validation Sequence

Use this sequence for each exchange read-only validation:

1. Confirm current GitHub CI and Docker Integration are green for the deployed commit.
2. Confirm backend health returns OK.
3. Log in as the intended test user.
4. Create the exchange account record with `trading_enabled=false`.
5. Store the API key through the encrypted credential form.
6. Confirm the UI shows credential configured status without secret values.
7. Run read-only verification.
8. Confirm the result is `authenticated=true` or the failure is clearly explained.
9. Confirm no order, cancel, transfer, withdrawal, or trading endpoint was called.
10. Delete the exchange-side API key.
11. Remove or deactivate the temporary platform account credential.
12. Record the result in a dated validation document if the test used real exchange authentication.

## Failure Handling

If a read-only check fails:

- Do not retry by enabling trading.
- Confirm exchange mode first: TESTNET/Demo/REAL.
- Confirm API key permission and passphrase where required.
- Confirm IP allowlist and server egress IP.
- Confirm clock sync on the Ubuntu host.
- Confirm the platform account mode matches the endpoint being tested.
- Delete any credential that may have been exposed or copied into an unsafe location.

## Acceptance Criteria

The stage is considered safe when:

- Read-only checks can pass without enabling trading.
- Failed read-only checks fail closed without side effects.
- No API secret material is returned to the frontend.
- Audit/log output contains no raw API secret, passphrase, signature, request header, or full exchange response.
- Account trading flags remain disabled.
- Temporary exchange API keys are deleted after validation.
