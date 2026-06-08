# Phase 3 Testnet Preparation

Phase 3 goal: prepare Binance Testnet, Bybit Testnet, and OKX Demo Trading integration without enabling live trading behavior by default.

This phase must preserve the safety rule that the platform default account mode remains `SIMULATION`.

## Official References Checked

- Binance Spot Testnet documentation: `https://developers.binance.com/docs/binance-spot-api-docs/testnet`
- Binance Spot API limits documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits`
- Binance signed endpoint security documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/request-security`
- Binance order endpoint documentation: `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints`
- Bybit V5 integration guidance: `https://bybit-exchange.github.io/docs/v5/guide`
- Bybit V5 rate limit documentation: `https://bybit-exchange.github.io/docs/v5/rate-limit`
- Bybit V5 create order documentation: `https://bybit-exchange.github.io/docs/v5/order/create-order`
- OKX API documentation and demo trading documentation: `https://www.okx.com/docs-v5/` and `https://www.okx.com/en-us/help/api-faq`
- OKX place order documentation: `https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order`

Notes from official documentation:

- Binance Spot Testnet is not always synchronized with live exchange and may be periodically reset.
- Binance signed requests use HMAC-SHA256 over the query string and send `X-MBX-APIKEY`.
- Binance order requests use a signed private trading endpoint and support client order IDs.
- Binance rate limits must use response headers and `/api/v3/exchangeInfo` rate-limit data as runtime sources of truth.
- Bybit Testnet REST base endpoint is `https://api-testnet.bybit.com`.
- Bybit V5 authenticated requests send `X-BAPI-API-KEY`, `X-BAPI-TIMESTAMP`, `X-BAPI-RECV-WINDOW`, and `X-BAPI-SIGN`.
- Bybit V5 order creation uses signed JSON request bodies and supports `orderLinkId` for client-side idempotency.
- Bybit default HTTP IP limit is 600 requests per 5-second window.
- OKX REST authentication sends `OK-ACCESS-KEY`, `OK-ACCESS-SIGN`, `OK-ACCESS-TIMESTAMP`, and `OK-ACCESS-PASSPHRASE`.
- OKX order creation uses signed JSON request bodies and supports `clOrdId` for client-side idempotency.
- OKX Demo Trading uses demo trading API keys and demo WebSocket endpoints. OKX documentation notes region-specific production domains; demo setup must be verified against the account region before use.
- OKX public REST limits are IP-scoped, private REST limits are User ID scoped, and trading limits can be shared across REST and WebSocket order channels.

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

Implemented in step 3:

- Exchange HTTP client protocol
- No-op HTTP client that fails closed
- Public adapter methods for server time and exchange info
- Public symbol rule normalization for Binance, Bybit, and OKX
- Fake-client tests for public connectivity mappings
- Interface expansion for `get_server_time()` and `get_exchange_info()`

Implemented in step 4:

- `ExchangeCredentials` value object for adapter-level credential injection
- Private HTTP client contract with explicit security type metadata
- Authenticated read-only balance and position method structure
- Binance, Bybit, and OKX fake-client balance normalization tests
- Bybit and OKX fake-client position normalization tests
- OKX Demo Trading signed request marker
- Adapter factory credential wiring

Implemented in step 5:

- Exchange rate-limit metadata model
- Binance, Bybit, and OKX static rate-limit configuration
- Adapter-level `rate_limit_config` exposure
- Tests for rate-limit scopes, headers, and conservative dynamic-source markers

Implemented in step 6:

- Testnet order preflight gate
- Explicit manual testnet order enable confirmation requirement
- Tests proving SIMULATION and REAL accounts are blocked
- Tests proving disabled adapters, disabled exchange-account trading, disabled risk trading, missing API key metadata, and missing manual confirmation all block testnet orders
- Tests proving the gate only approves when every safety condition is true

Implemented in step 7:

- Signed exchange HTTP client
- Injectable HTTP transport for tests and future runtime wiring
- Binance signed GET request preparation
- Bybit V5 signed GET request preparation
- OKX signed GET request preparation with demo trading header
- Tests proving signing payloads, headers, timestamps, and transport injection

Implemented in step 8:

- Signed POST request preparation for Binance, Bybit, and OKX
- Gate-protected testnet order request preparation service
- Exchange-specific testnet order payload mapping for Binance, Bybit, and OKX
- Client order ID mapping to `newClientOrderId`, `orderLinkId`, and `clOrdId`
- Tests proving blocked preflight gates cannot prepare order requests
- Tests proving LIMIT orders require an explicit price
- Tests proving prepared order requests use signed query or JSON bodies as expected

Implemented in step 9:

- Gate-protected testnet order execution service
- Explicit execution path through prepared signed requests
- Injectable transport execution hook for tests and future runtime wiring
- Tests proving approved gates can send through fake transport
- Tests proving blocked gates do not send any request
- Tests proving execution results do not expose request headers, params, or body

Implemented in step 10:

- Testnet order API request schema
- `/api/v1/orders/testnet/submit` endpoint wiring
- API preflight service with user-owned account lookup by `user_id`
- API key metadata-only check without decrypting or returning secrets
- Tests proving cross-user account access is blocked
- Tests proving failed gate conditions return blocked reasons
- Tests proving approved preflight can build an internal order context without exposing secrets
- Intentional `501 NOT_IMPLEMENTED` response after preflight until secret decryption and real testnet transport are enabled

Not implemented yet:

- Decrypting stored API secrets into adapter credentials
- Runtime rate-limit enforcement service
- Real exchange HTTP transport enablement for testnet order submission
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

## Testnet Order Request Preparation

The testnet order request service prepares exchange-specific signed POST requests only after the order preflight gate is approved.

- Binance maps client order IDs to `newClientOrderId`.
- Bybit maps client order IDs to `orderLinkId`.
- OKX maps client order IDs to `clOrdId`.
- LIMIT orders require an explicit price.
- The service returns a prepared request and does not send it.

## Testnet Order Execution Service

The testnet order execution service sends a prepared request only after the order preflight gate has already approved the request.

- Blocked gates raise before any transport call.
- The service returns exchange response data plus method and path metadata only.
- Request headers, params, body, API keys, and signatures are not exposed in the execution result.
- Current tests use fake transport only.
- Real testnet HTTP transport enablement remains intentionally unimplemented.

## Testnet Order API Endpoint

The testnet order API endpoint is wired at `/api/v1/orders/testnet/submit`.

- The endpoint requires normal JWT authentication through `get_current_user`.
- Account lookup is scoped by `user_id` and `exchange_account_id`.
- API key checks use metadata only and do not decrypt or return secrets.
- Blocked preflight gates return HTTP 400 with reasons.
- A fully approved preflight currently returns HTTP 501 by design.
- The 501 response prevents real testnet submission until secret decryption and real transport wiring are implemented.

## Adapter Safety Behavior

Current adapter skeletons behave as follows:

- `TESTNET_ADAPTERS_ENABLED=false` blocks all testnet read-only calls.
- Enabling testnet adapters without an HTTP client still fails closed.
- Public connectivity methods are only tested through fake clients.
- Authenticated read-only methods require injected credentials.
- Authenticated read-only methods are only tested through fake clients unless a signed client is explicitly injected.
- Rate-limit metadata is available but not enforced at runtime yet.
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

## Rate Limit Preparation

Current metadata exists only to prepare the future Rate Limit Service.

- Binance: tracks `Retry-After`, `X-MBX-USED-WEIGHT-*`, `X-MBX-ORDER-COUNT-*`, and marks `REQUEST_WEIGHT` / `ORDERS` as runtime values from `exchangeInfo` and response headers.
- Bybit: tracks `X-Bapi-Limit`, `X-Bapi-Limit-Status`, `X-Bapi-Limit-Reset-Timestamp`, the 600 requests / 5 seconds HTTP IP cap, WebSocket connection creation cap, and market-data connection cap.
- OKX: tracks IP-scoped public REST limits, User ID scoped private REST limits, REST/WebSocket shared order-management limits, and error code `50011` as a rate-limit signal.

Runtime enforcement is intentionally not active yet.

## Phase 3 Recommended Order

1. Add read-only adapter clients without order placement. Done.
2. Implement public connectivity checks: server time, exchange info, symbol rules. Done with fake-client tests.
3. Implement authenticated read-only structure: balances and positions. Done with fake-client tests.
4. Add adapter-specific rate-limit metadata. Done.
5. Add testnet order preflight gate behind explicit manual confirmation. Done.
6. Add signed HTTP client implementation for testnet read-only requests. Done.
7. Add gate-protected testnet order request preparation. Done.
8. Add gate-protected testnet order execution service. Done with fake-transport tests.
9. Add API endpoint preflight wiring for testnet-only order placement. Done with intentional 501 after preflight.
10. Add secret decryption and real testnet transport wiring behind the existing preflight gate.
11. Add WebSocket user stream connections for order and position updates.
12. Add reconciliation checks comparing exchange state, database state, and target state.

## Safety Rules Before Any Testnet Order

Before real testnet order submission is implemented, the platform must enforce:

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
