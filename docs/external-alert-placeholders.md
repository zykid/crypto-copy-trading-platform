# External Alert Senders

This module provides guarded Telegram, email, and webhook alert delivery. All channels remain disabled by default and only send when the matching `.env.prod` flag is explicitly enabled.

## Supported Channels

- Telegram Bot API
- Email through SMTP with STARTTLS
- Webhook POST with optional HMAC SHA-256 signature

## Environment Variables

All channels are disabled by default:

```bash
TELEGRAM_ALERTS_ENABLED=false
EMAIL_ALERTS_ENABLED=false
WEBHOOK_ALERTS_ENABLED=false
```

Shared timeout:

```bash
ALERT_TIMEOUT_SECONDS=5
```

Telegram:

```bash
TELEGRAM_BOT_TOKEN=replace-with-telegram-bot-token
TELEGRAM_CHAT_ID=replace-with-telegram-chat-id
```

Email:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=replace-with-smtp-password
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=ops@example.com
```

Webhook:

```bash
ALERT_WEBHOOK_URL=https://alerts.example.com/webhook
ALERT_WEBHOOK_SECRET=replace-with-webhook-secret
```

Dependency health monitoring is also disabled by default:

```bash
DEPENDENCY_HEALTH_MONITOR_ENABLED=false
DEPENDENCY_HEALTH_MONITOR_INTERVAL_SECONDS=60
DEPENDENCY_HEALTH_ALERT_THROTTLE_SECONDS=300
```

## Safety Rules

Do not send or log:

- API keys or API secrets
- encrypted secret blobs
- exchange responses containing sensitive account data
- exact balances, exact positions, or exact order quantities
- user email, username, or `user_id`
- copy trading relationships that identify users
- raw signal IDs, execution IDs, client order IDs, or exchange account IDs
- database passwords, database URLs, or backup file contents

External alerts should use coarse operational messages such as:

- service unhealthy
- reconciliation drift detected by severity
- rate-limit protection triggered
- emergency stop enabled
- backup failed
- order execution failed by safe terminal status and coarse failure type

## Current Implementation

`app.services.external_alerts` now includes:

- configuration validation through `build_external_alert_plan`
- redacted configuration summaries for diagnostics
- `send_external_alert` with per-channel failure isolation
- Telegram JSON POST delivery
- SMTP email delivery with STARTTLS
- webhook JSON POST delivery with optional `X-Alert-Signature`
- newline trimming and message length limits on alert event text
- timeout control through `timeout_seconds`

`app.services.operational_alerts` includes safe helpers for coarse operational events:

- `build_dependency_health_alert` converts dependency health check results into a `Service dependency health degraded` event that includes only component name, coarse status, and safe dependency names.
- `maybe_send_dependency_health_alert` sends that event through the guarded external alert sender and suppresses repeated dependency health alerts inside the throttle window.
- `build_emergency_stop_alert` converts emergency stop enablement into an `Emergency stop enabled` event with only component, scope, and new-orders-blocked metadata.
- `maybe_send_emergency_stop_alert` dispatches the safe emergency stop event and throttles repeated events by scope.
- `build_order_failure_alert` converts failed terminal order states into a coarse `Order execution failed` event with only component, terminal status, and safe failure type metadata.
- `maybe_send_order_failure_alert` dispatches the safe order failure event through the same guarded sender and throttles repeated events by terminal status and failure type.
- `build_rate_limit_alert` converts runtime rate-limit protection events into a `Rate limit protection triggered` event with only component, exchange, scope, request category, and bounded retry-after metadata.
- `maybe_send_rate_limit_alert` dispatches the safe rate-limit event and throttles repeated events by exchange, scope, and request category.

`app.services.operational_alert_runtime` provides a small runtime bridge for service integrations. It centralizes the external alert config, dispatch throttle state, timestamp source, and optional transports. Its notification methods keep alert delivery non-blocking and return an empty result when alert configuration or delivery fails, so trading safety decisions never depend on a third-party alert destination.

`app.api.v1.risk_settings` wires the emergency stop alert into the risk settings update path. When `trading_enabled` changes from `true` to `false`, the API emits only an account-scope `Emergency stop enabled` operational alert through the runtime bridge. The alert omits user IDs, account IDs, actor identity, symbols, balances, positions, orders, quantities, prices, and exchange responses. If alert delivery fails, the risk-setting update still succeeds so the trading stop is not blocked by an alert destination.

`app.api.v1.orders` wires order terminal failure alerts into manual signal execution. When the order engine stores a terminal `FAILED` execution because the order is risk-rejected or zero-quantity, it emits only terminal status and coarse failure type through the runtime bridge. The alert omits user IDs, account IDs, signal IDs, execution IDs, client order IDs, exchange order IDs, symbols, side, order type, quantities, prices, risk reasons, error messages, request paths, and exchange responses.

`app.services.rate_limit_service.RuntimeRateLimitService` can accept an optional operational alert runtime. When one is explicitly injected, repeated testnet order requests blocked by runtime rate-limit protection emit only safe rate-limit metadata: exchange name, coarse scope, request category, and bounded retry-after seconds. The alert payload omits exchange account IDs, request paths, user data, order IDs, quantities, prices, and exchange responses. The default global limiter still has no alert runtime attached.

`app.services.dependency_health_monitor` provides a disabled-by-default monitor tick helper. It validates interval and throttle settings, skips the health check provider while disabled, and reuses the guarded dependency health alert sender when explicitly enabled by runtime wiring.

`app.workers.dependency_health_monitor` provides a long-running worker entrypoint:

```bash
python -m app.workers.dependency_health_monitor
```

The worker reads the same disabled-by-default environment settings, converts dependency health endpoint details into safe status fields, suppresses repeated alerts through the throttle window, and does not touch trading execution flows.

`app.workers.external_alert_smoke_test` provides a synthetic delivery test command:

```bash
python -m app.workers.external_alert_smoke_test
```

The command reads the guarded external alert settings and sends only a synthetic `External alert smoke test` event when at least one channel is explicitly enabled. If all channels are disabled, it exits successfully without sending anything. The payload contains only `component=external_alerts` and `event_type=smoke_test` metadata.

The first wired delivery integration point is PostgreSQL backup failure reporting. The backup script sends only a coarse `PostgreSQL backup failed` event with component and error type metadata. Alert delivery errors do not change the backup job's failure code.

Reconciliation drift alert helpers are available for explicit service integration, but they do not automatically alter order execution behavior. When wired into trading flows, alert delivery must stay non-blocking and must not include user, account, order, quantity, price, signal, client order, request path, actor identity, or exchange response data.

## Operational Guidance

- Keep credentials in `.env.prod`, not GitHub.
- Rotate webhook and bot tokens if they are exposed.
- Prefer private channels or restricted recipients.
- Treat alert destinations as sensitive because alert content can reveal operational state.
- Test each destination with a synthetic operational alert before relying on it.
