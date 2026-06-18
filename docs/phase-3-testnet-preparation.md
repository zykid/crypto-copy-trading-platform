# Phase 3 Testnet Preparation

Phase 3 goal: prepare Binance Testnet, Bybit Testnet, and OKX Demo Trading integration without enabling live trading behavior by default.

This phase must preserve the safety rule that the platform default account mode remains `SIMULATION`.

## Official References Checked

- Binance Spot Testnet documentation: `https://developers.binance.com/docs/binance-spot-api-docs/testnet`
- Binance Spot API limits documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits`
- Binance signed endpoint security documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/request-security`
- Binance order endpoint documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints`
- Binance Spot User Data Stream documentation: `https://developers.binance.com/docs/binance-spot-api-docs/user-data-stream`
- Bybit V5 integration guidance: `https://bybit-exchange.github.io/docs/v5/guide`
- Bybit V5 rate limit documentation: `https://bybit-exchange.github.io/docs/v5/rate-limit`
- Bybit V5 create order documentation: `https://bybit-exchange.github.io/docs/v5/order/create-order`
- Bybit V5 WebSocket connection documentation: `https://bybit-exchange.github.io/docs/v5/ws/connect`
- OKX API documentation and demo trading documentation: `https://www.okx.com/docs-v5/` and `https://www.okx.com/en-us/help/api-faq`
- OKX place order documentation: `https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order`

Notes from official documentation:

- Binance Spot Testnet is not always synchronized with live exchange and may be periodically reset.
- Binance signed requests use HMAC-SHA256 over the query string and send `X-MBX-APIKEY`.
- Binance order requests use a signed private trading endpoint and support client order IDs.
- Binance user data streams require a listenKey before opening the stream WebSocket.
- Binance rate limits must use response headers and `/api/v3/exchangeInfo` rate-limit data as runtime sources of truth.
- Bybit Testnet REST base endpoint is `https://api-testnet.bybit.com`.
- Bybit V5 authenticated requests send `X-BAPI-API-KEY`, `X-BAPI-TIMESTAMP`, `X-BAPI-RECV-WINDOW`, and `X-BAPI-SIGN`.
- Bybit V5 WebSocket authentication signs `GET/realtime{expires}`.
- Bybit V5 order creation uses signed JSON request bodies and supports `orderLinkId` for client-side idempotency.
- Bybit default HTTP IP limit is 600 requests per 5-second window.
- OKX REST authentication sends `OK-ACCESS-KEY`, `OK-ACCESS-SIGN`, `OK-ACCESS-TIMESTAMP`, and `OK-ACCESS-PASSPHRASE`.
- OKX WebSocket login signs `timestamp + GET + /users/self/verify`.
- OKX order creation uses signed JSON request bodies and supports `clOrdId` for client-side idempotency.
- OKX Demo Trading uses demo trading API keys and demo WebSocket endpoints. OKX documentation notes region-specific production domains; demo setup must be verified against the account region before use.
- OKX public REST limits are IP-scoped, private REST limits are User ID scoped, and trading limits can be shared across REST and WebSocket order channels.

## Current Phase 3 Scope

Implemented so far:

- Testnet endpoint configuration constants and readiness gate.
- Binance, Bybit, and OKX adapter skeletons, disabled by default.
- Public connectivity method structure for server time, exchange info, and symbol rules.
- Authenticated read-only balance and position method structure with fake-client tests.
- Exchange rate-limit metadata for Binance, Bybit, and OKX.
- Testnet order preflight gate with explicit manual confirmation.
- Signed GET and POST HTTP request preparation for Binance, Bybit, and OKX.
- Gate-protected testnet order request preparation and execution services.
- `/api/v1/orders/testnet/submit` endpoint with user-owned account lookup by `user_id`.
- Internal encrypted API key loading into `ExchangeCredentials` after preflight approval.
- Real testnet/demo REST transport wiring behind the existing preflight gate.
- Runtime rate-limit enforcement before testnet order HTTP submission.
- Redis-backed distributed runtime rate-limit counters with fail-closed behavior.
- Testnet private user stream connection plan generation.
- Testnet user stream lifecycle and event parser shell with injected fake socket tests.
- Position reconciliation snapshot comparison service.
- Reconciliation audit, system-event, and notification hook plan generation.
- Persistent reconciliation audit, system event, and internal notification storage.
- Reconciliation worker orchestration with tenant-scoped database snapshots and injected exchange/target providers.

Not implemented yet:

- Real WebSocket transport implementation.
- Continuous WebSocket event consumption loop.
- Balance or position synchronization writes.
- External notification delivery.
- Automatic reconciliation repair.

## Endpoint Preparation

Configured endpoint metadata:

| Exchange | Mode | REST | Public WebSocket | Private WebSocket |
| --- | --- | --- | --- | --- |
| Binance | Spot Testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision/ws` | listenKey-based |
| Bybit | Testnet | `https://api-testnet.bybit.com` | `wss://stream-testnet.bybit.com/v5/public/spot` | `wss://stream-testnet.bybit.com/v5/private` |
| OKX | Demo Trading | `https://openapi.okx.com` | `wss://wspap.okx.com:8443/ws/v5/public` | `wss://wspap.okx.com:8443/ws/v5/private` |

## Safety Gate

The readiness gate returns `READY` only when all are true:

- Exchange has a configured testnet/demo endpoint.
- Account mode is exactly `TESTNET`.
- Account `trading_enabled` is false during readiness checks.
- API key metadata is configured.

This intentionally separates readiness checks from order placement.

## Testnet Order Gate

The order preflight gate returns `APPROVED` only when all are true:

- Exchange has configured testnet/demo routing.
- Account mode is exactly `TESTNET`.
- `TESTNET_ADAPTERS_ENABLED` is true.
- Exchange account `trading_enabled` is true.
- Risk settings `trading_enabled` is true.
- Testnet API key metadata is configured.
- Manual testnet order enable confirmation has been recorded.

The gate is a pure preflight check. It does not submit orders and does not talk to an exchange by itself.

## Signed HTTP Client

The signed HTTP client can prepare and execute authenticated GET and POST requests when explicitly injected.

- Default adapters still use `NoopExchangeHttpClient` and fail closed.
- The client does not retrieve or decrypt API secrets by itself.
- Tests use an injected transport and do not perform network requests.
- Secret values must never be logged or returned to the frontend.
- Transport errors are wrapped in a generic RuntimeError before API conversion.

## Internal Credential Loading

The credential loader decrypts stored API key fields only inside backend services.

- Lookup is scoped by `user_id` and `exchange_account_id`.
- Missing credentials return `None`.
- Another user cannot load the owner's credentials.
- Decrypted values are only returned as internal `ExchangeCredentials` objects.
- Decrypted API secret values are not included in Pydantic response schemas.

## Testnet Order Request Preparation

The testnet order request service prepares exchange-specific signed POST requests only after the order preflight gate is approved.

- Binance maps client order IDs to `newClientOrderId`.
- Bybit maps client order IDs to `orderLinkId`.
- OKX maps client order IDs to `clOrdId`.
- LIMIT orders require an explicit price.
- The service returns a prepared request and does not send it.

## Runtime Rate Limit Service

The runtime rate-limit service is now connected to testnet order execution before the HTTP transport call.

- A conservative per-account safety rule allows one testnet order request per second per exchange account and endpoint.
- Concrete static exchange metadata is also enforced when the rule has both `limit` and `interval_seconds`.
- Unknown dynamic limits remain documented metadata and are not guessed as hard exchange limits.
- If a rate limit is exceeded, the API returns HTTP 429 with a `Retry-After` header.
- If rate limiting blocks a request, no exchange HTTP request is sent.
- Runtime counters use Redis so multiple backend processes share the same windows.
- Redis errors fail closed and the API returns HTTP 503 before any exchange request is sent.
- In-memory counters remain available only for isolated unit tests.

## Testnet User Stream Connection Plans

The user stream service can prepare private WebSocket connection material without opening a socket.

- Binance prepares the REST listenKey request and a placeholder WebSocket URL containing `{listenKey}`.
- Bybit prepares the private WebSocket URL and auth message.
- OKX prepares the private WebSocket URL and login message.
- API secrets are used only to compute signatures and are not stored in the returned plan.
- Tests verify the prepared signatures and ensure the API secret does not appear in the plan string.

## Testnet User Stream Runtime Shell

The runtime shell defines lifecycle and parsing behavior without real exchange connectivity.

- Socket behavior is behind an injected `TestnetUserStreamSocketClient` protocol.
- Tests use fake socket clients and do not open real network connections.
- Session states include `CONNECTED`, `AUTHENTICATED`, `CLOSED`, and `FAILED`.
- Bybit and OKX login messages are sent through the injected client when present.
- Binance sessions connect without a WebSocket login message after listenKey preparation.
- Event parsing currently classifies raw payloads into `ORDER`, `BALANCE`, `POSITION`, or `UNKNOWN`.
- Parsed events keep raw payloads only and do not write balances, positions, or orders to the database.

## Position Reconciliation Preparation

The reconciliation service compares exchange, database, and target position snapshots.

- Inputs are explicit snapshots supplied by the caller.
- Symbols are normalized to uppercase and duplicate snapshots are combined per source.
- The service compares exchange vs database, exchange vs target, and database vs target quantities.
- Reports include `MATCHED` or `DRIFT_DETECTED` status.
- Difference severity is `WARNING` or `CRITICAL` depending on configured thresholds.
- Quantity tolerance can suppress tiny rounding differences.
- Reports always set `auto_fix_allowed=False` in this phase.
- The service does not call exchanges, write database rows, place orders, or auto-repair drift.

## Reconciliation Hook Plans

The reconciliation hook service converts reconciliation reports into side-effect-free plans.

- Every report produces an audit entry plan.
- Matched reports produce no system event and no notification plan.
- Drifted reports produce a system event plan and one notification plan per requested channel.
- Supported notification channels are `INTERNAL`, `TELEGRAM`, `EMAIL`, and `WEBHOOK`.
- External channels are reserved plans only; no external message is sent in this phase.
- Payload quantities are serialized as strings to avoid Decimal precision loss.
- Payloads include user and exchange account identifiers, status, severity, and differences only.
- Payloads do not include API keys, API secrets, passphrases, signatures, or request headers.
- Hook plans always set `auto_fix_allowed=False` in this phase.

## Reconciliation Persistence

The reconciliation persistence service stores hook plans in database-backed observability tables.

- `audit_logs` records every reconciliation hook plan and is intended as append-only storage.
- `system_events` records drift events only.
- `internal_notifications` records internal notification plans only.
- External notification channels remain reserved and are not sent or stored as internal messages.
- The service adds records and flushes the active SQLAlchemy session without committing it.
- Transaction ownership remains with the caller, so future workers can rollback related writes together.
- The persistence service does not update or delete audit log rows.
- Stored payloads retain the same secret-free structure produced by the hook-plan service.

## Reconciliation Worker Orchestration

The reconciliation worker composes snapshot collection, comparison, hook planning, and persistence.

- Exchange and target snapshots are supplied through injected providers.
- Database snapshots are filtered by both `user_id` and `exchange_account_id`.
- Provider failures propagate before any audit log, system event, or notification is written.
- Drift alerts receive status, severity, and difference count only.
- The worker flushes observability records but does not commit the caller's transaction.
- Worker, report, and hook plan all keep `auto_fix_allowed=False`.
- The worker does not place orders, update positions, or repair drift.

## Testnet Order Execution Service

The testnet order execution service sends a prepared request only after the order preflight gate and runtime rate-limit checks approve the request.

- Blocked gates raise before any transport call.
- Rate-limit blocks raise before any transport call.
- The service returns exchange response data plus method and path metadata only.
- Request headers, params, body, API keys, and signatures are not exposed in the execution result.
- Tests use fake or injected transports and do not perform network requests.
- Runtime API execution uses real testnet/demo REST endpoints only after all preflight gates pass.

## Testnet Order API Endpoint

The testnet order API endpoint is wired at `/api/v1/orders/testnet/submit`.

- The endpoint requires normal JWT authentication through `get_current_user`.
- Account lookup is scoped by `user_id` and `exchange_account_id`.
- API key checks use metadata before internal credential loading.
- Blocked preflight gates return HTTP 400 with reasons.
- Runtime rate-limit blocks return HTTP 429 with `Retry-After`.
- Rate-limit store outages return HTTP 503 before any exchange request is sent.
- Runtime exchange failures return HTTP 502 with a generic error message.
- Successful responses do not include request headers, params, body, API keys, or signatures.

## Adapter Safety Behavior

Current adapter skeletons behave as follows:

- `TESTNET_ADAPTERS_ENABLED=false` blocks all testnet read-only and order-submission calls.
- Enabling testnet adapters without passing all order gates still fails closed.
- Public connectivity methods are only tested through fake clients.
- Authenticated read-only methods require injected credentials.
- Authenticated read-only methods are only tested through fake clients unless a signed client is explicitly injected.
- Runtime rate-limit enforcement is active for the testnet order API path.
- User stream support is limited to connection-plan generation and injected lifecycle shell tests.
- Position reconciliation support is limited to snapshot comparison reports, hook plans, and persistence.
- MockExchange remains the only adapter that can execute SIMULATION orders in the current codebase.

## Required API Key Rules

For testnet/demo API keys:

- Use dedicated testnet/demo accounts only.
- Do not reuse production API keys.
- Disable withdrawal permission where the exchange UI exposes it.
- Prefer IP restrictions where supported.
- Store secrets only through the existing encrypted API key system.
- Never commit API keys or secrets to GitHub.
- Never write API secrets to logs.

## Rate Limit Preparation

Current metadata supports runtime enforcement backed by Redis.

- Binance: tracks `Retry-After`, `X-MBX-USED-WEIGHT-*`, `X-MBX-ORDER-COUNT-*`, and marks `REQUEST_WEIGHT` / `ORDERS` as runtime values from `exchangeInfo` and response headers.
- Bybit: tracks `X-Bapi-Limit`, `X-Bapi-Limit-Status`, `X-Bapi-Limit-Reset-Timestamp`, the 600 requests / 5 seconds HTTP IP cap, WebSocket connection creation cap, and market-data connection cap.
- OKX: tracks IP-scoped public REST limits, User ID scoped private REST limits, REST/WebSocket shared order-management limits, and error code `50011` as a rate-limit signal.

Runtime enforcement applies conservative testnet order throttling and concrete static REST rules through Redis-backed counters. Dynamic header-driven updates remain intentionally deferred.

## Phase 3 Recommended Order

1. Add read-only adapter clients without order placement. Done.
2. Implement public connectivity checks: server time, exchange info, symbol rules. Done with fake-client tests.
3. Implement authenticated read-only structure: balances and positions. Done with fake-client tests.
4. Add adapter-specific rate-limit metadata. Done.
5. Add testnet order preflight gate behind explicit manual confirmation. Done.
6. Add signed HTTP client implementation for testnet read-only requests. Done.
7. Add gate-protected testnet order request preparation. Done.
8. Add gate-protected testnet order execution service. Done with fake-transport tests.
9. Add API endpoint preflight wiring for testnet-only order placement. Done.
10. Add internal secret decryption into `ExchangeCredentials`. Done.
11. Add real testnet transport wiring behind the existing preflight gate. Done.
12. Add runtime rate-limit enforcement. Done with Redis-backed fail-closed testnet order enforcement.
13. Add WebSocket user stream connection plans. Done without opening real sockets.
14. Add WebSocket socket lifecycle and event parser shell. Done with injected fake-client tests.
15. Add reconciliation checks comparing exchange state, database state, and target state. Done with snapshot tests.
16. Add reconciliation audit/event recording and notification hooks. Done with hook-plan tests.
17. Add persistent audit/system-event writes and internal notification storage. Done with persistence tests.
18. Add reconciliation worker orchestration around snapshot providers and persistence. Done with tenant-scoped database snapshots and injected providers.

## Safety Rules Before Any Testnet Order

Before real testnet order submission can pass, the platform must enforce:

- Account mode must be `TESTNET`.
- `TESTNET_ADAPTERS_ENABLED` must be true.
- Exchange account must have `trading_enabled = true`.
- Risk settings must have `trading_enabled = true`.
- A per-account explicit testnet enable action must be recorded in audit logs.
- The order must pass all existing risk checks.
- Runtime rate-limit checks must pass.
- The adapter must support idempotent `client_order_id`.
- The adapter must never run when account mode is `REAL`.

## Current Validation

Run on latest commit:

- `CI`
- `Docker Integration`

Both must stay green after this preparation step.
