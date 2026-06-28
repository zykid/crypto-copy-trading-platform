# Phase 3 Read-Only Validation Template - YYYY-MM-DD

Use this template for every TESTNET, demo, or guarded REAL read-only exchange validation.

Do not store API keys, API secrets, passphrases, JWTs, signatures, request headers, raw exchange responses, database dumps, screenshots containing credentials, or full account identifiers in this document.

## Scope

- Date:
- Operator:
- Host:
- Deployed commit SHA:
- Frontend URL:
- Backend API prefix:
- Exchange:
- Exchange environment: TESTNET / Demo / REAL
- Operation: authenticated read-only balance / authenticated read-only position / public connectivity only
- Platform account mode:
- Platform `trading_enabled`:
- Risk setting `trading_enabled`:
- API key permission summary:
- API key withdrawal permission disabled: Yes / No / Not available in exchange UI
- API key IP allowlist enabled: Yes / No / Not available in exchange UI

No order placement, cancellation, transfer, withdrawal, strategy execution, copy trading, webhook execution, AI signal execution, account trading enablement, or automatic repair execution was performed.

## Preflight

| Check | Result | Notes |
| --- | --- | --- |
| Current GitHub CI is green for deployed commit |  |  |
| Current Docker Integration is green for deployed commit |  |  |
| Backend health endpoint is OK |  |  |
| Frontend is reachable |  |  |
| Logged-in user owns the exchange account record |  |  |
| Account mode matches exchange environment |  |  |
| Platform `trading_enabled=false` before test |  |  |
| Risk setting `trading_enabled=false` before test |  |  |
| API key secret material is not visible in UI |  |  |

## Validation Results

| Check | Result | Notes |
| --- | --- | --- |
| Encrypted credential storage |  |  |
| Password reauthentication before credential write |  |  |
| Read-only authentication request |  |  |
| Read-only balance result bounded |  |  |
| Read-only position result bounded |  |  |
| Safe frontend response without secret material |  |  |
| Safe backend log output without secret material |  |  |
| Account trading switch remained disabled |  |  |
| No order/cancel/transfer endpoint was called |  |  |
| Audit event recorded |  |  |

## Result Summary

- Authentication result: Passed / Failed / Not run
- Balance asset count:
- Position count:
- Failure category if failed: credential / passphrase / IP allowlist / endpoint mode / clock sync / exchange unavailable / platform bug / unknown
- Bounded error message:

## Cleanup

| Cleanup Item | Result | Notes |
| --- | --- | --- |
| Exchange-side temporary API key deleted |  |  |
| Platform encrypted credential removed or deactivated |  |  |
| Temporary exchange account record deactivated if no longer needed |  |  |
| Platform `trading_enabled` confirmed false after test |  |  |
| Risk setting `trading_enabled` confirmed false after test |  |  |
| Cleanup audit event recorded |  |  |

## Safety Conclusion

This validation confirms only the bounded read-only authentication and data retrieval path described above.

It does not approve TESTNET order submission, REAL order submission, copy trading, strategy trading, webhook trading, AI trading, automatic reconciliation repair execution, or production operation with funds.

## Follow-Up

- Required fix before next validation:
- Required operator action:
- Next approved validation step:
