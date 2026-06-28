# Phase 3 TESTNET Order Validation Result

Copy this template into a dated result file before any approved TESTNET order window.

Recommended filename:

```text
docs/phase-3-testnet-order-validation-YYYYMMDD.md
```

This document records the result of a controlled TESTNET or exchange demo order validation.

It does not authorize REAL trading.

## Validation Summary

- Date:
- Operator:
- Reviewer:
- Approval reference:
- Git commit:
- Environment:
- Frontend URL:
- Backend API URL:
- Exchange:
- Account mode: `TESTNET`
- Signal source: `manual`
- Validation result: `PASS` / `FAIL` / `ABORTED`

## Approval Gate

Record the explicit approval that allowed this temporary order window.

- Approval received: `yes` / `no`
- Approved by:
- Approval time:
- Approved window start:
- Approved window end:
- Maximum order count:
- Maximum notional:
- Approved symbol:

If approval is missing, stop. Do not submit an order.

## Pre-Window Checks

All checks must be `PASS` before enabling any order path.

| Check | Result | Evidence |
| --- | --- | --- |
| `CI` green for deployed commit |  |  |
| `Docker Integration` green for deployed commit |  |  |
| Ubuntu deployment healthy |  |  |
| Database backup path writable |  |  |
| Audit log write verified |  |  |
| Emergency stop available |  |  |
| Account belongs to expected user |  |  |
| Account mode is `TESTNET` |  |  |
| Exchange account trading disabled before window |  |  |
| Risk setting trading disabled before window |  |  |
| API key is dedicated to testnet/demo |  |  |
| Withdrawal permission disabled |  |  |
| IP restriction confirmed where supported |  |  |
| Copy trading disabled |  |  |
| Strategy trading disabled |  |  |
| Webhook trading disabled |  |  |
| AI trading disabled |  |  |
| Reconciliation auto-repair execution disabled |  |  |

## Temporary Enablement

Record every temporary change.

| Change | Previous Value | Temporary Value | Changed By | Time | Rollback Owner |
| --- | --- | --- | --- | --- | --- |
| `TESTNET_ADAPTERS_ENABLED` | `false` | `true` |  |  |  |
| Exchange account `trading_enabled` | `false` | `true` |  |  |  |
| Risk setting `trading_enabled` | `false` | `true` |  |  |  |

Audit event IDs:

- Adapter enable event:
- Account trading enable event:
- Risk trading enable event:
- Manual confirmation event:

If any audit event is missing, stop. Do not submit an order.

## Risk Configuration

| Setting | Value | Evidence |
| --- | --- | --- |
| Symbol allowlist |  |  |
| Single-order notional cap |  |  |
| Maximum position cap |  |  |
| Maximum leverage |  |  |
| Minimum quantity |  |  |
| Maximum quantity |  |  |
| Runtime rate-limit rule |  |  |

## Order Request

- `signal_id`:
- `execution_id`:
- `exchange_account_id`:
- `client_order_id`:
- Symbol:
- Side:
- Order type:
- Quantity:
- Price:
- Notional:
- Reduce only:
- Submitted by:
- Submission time:

## Risk Engine Result

- Decision: `PASSED` / `REJECTED`
- Reasons:
- Risk log ID:
- Audit log ID:

If the risk result is not `PASSED`, stop. Do not submit the order.

## Exchange Submission Result

- Submission attempted: `yes` / `no`
- Adapter:
- Exchange request ID:
- Exchange order ID:
- Initial order status:
- Error message:
- Sanitized exchange response:

Do not paste API keys, secrets, passphrases, signatures, full headers, or full raw exchange responses.

## Order State Timeline

| Time | State | Source | Evidence |
| --- | --- | --- | --- |
|  | `CREATED` |  |  |
|  | `RISK_PASSED` |  |  |
|  | `SUBMITTED` |  |  |
|  | `ACCEPTED` |  |  |
|  | `PARTIALLY_FILLED` |  |  |
|  | `FILLED` |  |  |
|  | `CANCELLED` |  |  |
|  | `REJECTED` |  |  |
|  | `FAILED` |  |  |
|  | `TIMEOUT` |  |  |

Remove states that did not occur. Record unexpected states.

## Idempotency Check

| Check | Result | Evidence |
| --- | --- | --- |
| `signal_id + exchange_account_id` unique |  |  |
| Duplicate execution attempt rejected |  |  |
| `client_order_id` recorded |  |  |
| Retry did not create a second order |  |  |

## Rate Limit Observation

- Runtime limiter decision:
- Exchange header evidence:
- Redis limiter key:
- Retry-after or reset time:
- Rate-limit errors:

## Balance And Position Observation

Before order:

- Balance summary:
- Exchange position:
- Database position:
- Target position:

After order:

- Balance summary:
- Exchange position:
- Database position:
- Target position:

## Reconciliation Result

- Reconciliation run time:
- Report ID:
- Severity:
- Differences:
- Automatic repair attempted: `no`

Automatic repair must remain disabled.

## Cleanup

All cleanup checks must be recorded.

| Cleanup Item | Result | Evidence |
| --- | --- | --- |
| `TESTNET_ADAPTERS_ENABLED=false` restored |  |  |
| Exchange account `trading_enabled=false` restored |  |  |
| Risk setting `trading_enabled=false` restored |  |  |
| Copy trading remains disabled |  |  |
| Strategy trading remains disabled |  |  |
| Webhook trading remains disabled |  |  |
| AI trading remains disabled |  |  |
| Temporary exchange API key deleted or scheduled for deletion |  |  |
| Platform credential deactivated or retained with justification |  |  |
| Final reconciliation completed |  |  |
| Audit logs reviewed for secret leakage |  |  |

## Final Decision

- Final result: `PASS` / `FAIL` / `ABORTED`
- Reason:
- Follow-up required:
- Follow-up owner:
- Follow-up due date:

## Hard Stop Review

Confirm no hard stop condition occurred.

If any item is `yes`, final result must be `FAIL` or `ABORTED`.

| Condition | Yes/No | Evidence |
| --- | --- | --- |
| REAL endpoint targeted |  |  |
| Non-test account used |  |  |
| Withdrawal permission detected |  |  |
| Secret leaked to frontend, logs, screenshots, or docs |  |  |
| Duplicate order attempted unexpectedly |  |  |
| Rate limiter blocked request |  |  |
| Risk engine rejected request |  |  |
| Unexpected order state observed |  |  |
| Reconciliation drift unexpected |  |  |
| Emergency stop failed |  |  |

## Notes

Add only sanitized operational notes here.

Do not include API keys, API secrets, passphrases, signatures, full request headers, or full raw exchange responses.
