# TESTNET and REAL Mode Safety Runbook

This runbook confirms that TESTNET adapters are disabled by default and REAL trading remains unavailable until a later, separately approved phase.

## Default State

Production defaults must remain:

```bash
TESTNET_ADAPTERS_ENABLED=false
```

Account mode may exist as data, but operational readiness does not authorize REAL order execution.

## Pre-TESTNET Checks

Before any testnet phase:

1. Confirm the current phase explicitly allows TESTNET.
2. Use dedicated testnet API keys only.
3. Keep withdrawal permissions disabled where the exchange UI exposes that setting.
4. Confirm `.env.prod` is not used for testnet experiments unless the deployment is a dedicated staging environment.
5. Confirm `TESTNET_ADAPTERS_ENABLED=true` is a deliberate, temporary change.

Before any TESTNET order submission, complete `docs/phase-3-testnet-order-admission-checklist.md` and obtain separate explicit approval for the order window.

## Disable TESTNET Adapters

To return to the safe default:

```bash
TESTNET_ADAPTERS_ENABLED=false
```

Restart only the affected services through the normal production Compose workflow and verify metrics:

```bash
curl -s 'http://<server-tailscale-ip>:9090/api/v1/query?query=trading_testnet_adapters_enabled'
```

Expected value: `0`.

## REAL Mode Confirmation

Before production approval, confirm all of the following remain true:

- No production runbook instructs operators to enable REAL trading.
- No `.env.example` or `.env.prod.example` contains real exchange credentials.
- API key secrets are never displayed by the API, logs, docs, or alerts.
- External alerts do not include user, account, signal, order, balance, position, or exchange response data.
- `trading_real_trading_enabled` remains `0` in Prometheus.

## Later REAL Phase Requirements

REAL mode requires a separate small-funds validation plan:

- Dedicated test accounts.
- Dedicated API keys.
- Withdrawal permission disabled.
- Small notional caps.
- Emergency stop verified.
- Fresh backup and restore drill completed.
- API keys deleted after test completion.

This repository state does not complete or authorize that phase.
