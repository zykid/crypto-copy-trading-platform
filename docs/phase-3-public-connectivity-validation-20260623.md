# Phase 3 Public Connectivity Validation - 2026-06-23

This record documents credential-free public endpoint checks from the temporary Ubuntu integration server. No account API key was configured and no authenticated request or order request was sent.

## Results

| Exchange | Endpoint category | Result |
| --- | --- | --- |
| Binance Spot Testnet | Server time | Passed through the platform HTTP client |
| Bybit Testnet | Server time | Passed through the platform HTTP client |
| OKX | Public server time using normal host DNS | Blocked by the test network transport path |
| OKX | Public server time using a one-time direct route | Passed |

The normal Ubuntu DNS path resolved `www.okx.com` to the transparent proxy fake-IP range and the TLS handshake timed out. The platform classified this as a bounded `transport_error`. A one-time direct route confirmed that the OKX public endpoint itself was reachable. No `/etc/hosts`, Compose, application, or persistent DNS override was retained.

## Safety State

During verification, monitoring exposed that `TESTNET_ADAPTERS_ENABLED` was still enabled from an earlier test. The Ubuntu `.env` value was restored to `false`, the backend was recreated, and the following metrics were verified:

```text
trading_real_trading_enabled 0
trading_testnet_adapters_enabled 0
```

The backend container returned to `running healthy` after the configuration correction.

## Required Network Follow-Up

Do not hard-code an exchange CDN address in application code or persistent Compose configuration. Before OKX testnet/demo authentication is attempted again, configure the network proxy or DNS layer so `www.okx.com` receives a routable real address and preserves TLS server-name validation. Re-run the credential-free public endpoint check before storing any new credential.

This validation does not authorize TESTNET or REAL order execution.
