# Phase 3 Testnet Preparation

Phase 3 goal: prepare Binance Testnet, Bybit Testnet, and OKX Demo Trading integration without enabling live trading behavior by default.

This phase must preserve the safety rule that the platform default account mode remains `SIMULATION`.

## Official References Checked

- Binance Spot Testnet documentation: `https://developers.binance.com/docs/binance-spot-api-docs/testnet`
- Bybit API documentation testnet endpoint: `https://bybit-exchange.github.io/docs/v3/intro`
- OKX API documentation and demo trading documentation: `https://www.okx.com/docs-v5/` and `https://www.okx.com/en-us/help/api-faq`

Notes from official documentation:

- Binance Spot Testnet is not always synchronized with live exchange and may be periodically reset.
- Bybit Testnet REST base endpoint is `https://api-testnet.bybit.com`.
- OKX Demo Trading uses demo trading API keys and demo WebSocket endpoints. OKX documentation notes region-specific production domains; demo setup must be verified against the account region before use.

## Current Phase 3 Scope

Implemented in step 1:

- Testnet endpoint configuration constants
- Testnet readiness gate
- Unit tests for safety gate behavior
- `.env.example` entries with testnet adapters disabled by default
- Documentation for next implementation steps

Implemented in step 2:

- `BinanceAdapter` skeleton
- `BybitAdapter` skeleton
- `OKXAdapter` skeleton
- Read-only testnet adapter base class
- Adapter factory
- Tests proving testnet adapters are disabled by default
- Tests proving testnet trading methods are not implemented

Not implemented yet:

- Real HTTP calls to exchanges
- Authenticated exchange requests
- Testnet order placement
- WebSocket connections
- Balance or position synchronization

## Endpoint Preparation

Configured endpoint metadata:

| Exchange | Mode | REST | Public WebSocket | Private WebSocket |
| --- | --- | --- | --- | --- |
| Binance | Spot Testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision/ws` | pending |
| Bybit | Testnet | `https://api-testnet.bybit.com` | `wss://stream-testnet.bybit.com/v5/public/spot` | `wss://stream-testnet.bybit.com/v5/private` |
| OKX | Demo Trading | `https://openapi.okx.com` | `wss://wspap.okx.com:8443/ws/v5/public` | `wss://wspap.okx.com:8443/ws/v5/private` |

## Safety Gate

The readiness gate returns `READY` only when all are true:

- Exchange has a configured testnet/demo endpoint.
- Account mode is exactly `TESTNET`.
- Account `trading_enabled` is false during readiness checks.
- API key metadata is configured.

This intentionally separates readiness checks from order placement.

## Adapter Safety Behavior

Current adapter skeletons behave as follows:

- `TESTNET_ADAPTERS_ENABLED=false` blocks all testnet read-only calls.
- Enabling testnet adapters still does not perform HTTP calls yet.
- `place_order()` and `cancel_order()` raise immediately for testnet/demo adapters.
- MockExchange remains the only adapter that can execute orders in the current codebase.

## Required API Key Rules

For testnet/demo API keys:

- Use dedicated testnet/demo accounts only.
- Do not reuse production API keys.
- Disable withdrawal permission where the exchange UI exposes it.
- Prefer IP restrictions where supported.
- Store secrets only through the existing encrypted API key system.
- Never commit API keys or secrets to GitHub.
- Never write API secrets to logs.

## Phase 3 Recommended Order

1. Add read-only adapter clients without order placement. Done.
2. Implement public connectivity checks: server time, exchange info, symbol rules.
3. Implement authenticated read-only checks: balances and positions.
4. Add adapter-specific rate-limit metadata.
5. Add testnet-only order placement behind explicit manual gate.
6. Add WebSocket user stream connections for order and position updates.
7. Add reconciliation checks comparing exchange state, database state, and target state.

## Safety Rules Before Any Testnet Order

Before testnet order placement is implemented, the platform must enforce:

- Account mode must be `TESTNET`.
- `TESTNET_ADAPTERS_ENABLED` must be true.
- Exchange account must have `trading_enabled = true`.
- Risk settings must have `trading_enabled = true`.
- A per-account explicit testnet enable action must be recorded in audit logs.
- The order must pass all existing risk checks.
- The adapter must support idempotent `client_order_id`.
- The adapter must never run when account mode is `REAL`.

## Current Validation

Run on latest commit:

- `CI`
- `Docker Integration`

Both must stay green after this preparation step.
