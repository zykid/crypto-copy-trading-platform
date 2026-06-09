# Phase 3 Redis Rate Limit Counters

This note records the Phase 3 Redis-backed runtime rate-limit counter boundary.

The Redis store is a counter backend only. It does not enable testnet adapters, submit orders, change account modes, bypass risk checks, or change the existing manual testnet order gate.

## Implemented Scope

- Added a `RateLimitWindowStore` protocol for runtime rate-limit counters.
- Kept `InMemoryRateLimitWindowStore` as the default for GitHub and mock integration tests.
- Added `RedisRateLimitWindowStore` for distributed counters in multi-process deployments.
- `RuntimeRateLimitService` can now receive an injected store.
- Existing testnet order execution still calls the same rate-limit service before HTTP submission.

## Safety Boundary

- The default singleton still uses in-memory counters unless Redis is explicitly injected.
- Redis keys contain exchange name, rule name, account or global scope, and request path only.
- Redis keys do not include API keys, secrets, passphrases, signatures, request headers, or request bodies.
- Rate-limit failures still raise before exchange HTTP transport is called.
- The store is intentionally conservative: exceeding a counter blocks the order attempt.

## Validation

Covered by backend tests:

- Repeated testnet order requests are blocked in the same safety window.
- In-memory windows reset after the configured interval.
- Safety rules remain scoped per exchange account.
- Redis-backed counters set a TTL for the new window.
- Runtime rate limiting can use the Redis store through dependency injection.
