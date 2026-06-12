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

`app.services.dependency_health_monitor` provides a disabled-by-default monitor tick helper. It validates interval and throttle settings, skips the health check provider while disabled, and reuses the guarded dependency health alert sender when explicitly enabled by runtime wiring.

The first wired delivery integration point is PostgreSQL backup failure reporting. The backup script sends only a coarse `PostgreSQL backup failed` event with component and error type metadata. Alert delivery errors do not change the backup job's failure code.

Dependency health dispatch now has a service-level monitor tick helper, but it is not yet attached to a long-running production loop or separate monitor process. Future wiring should keep it disabled by default, preserve rate limiting, and stay separate from trading execution flows.

The sender is intentionally not wired into trading flows yet. Future integration points must pass only coarse operational events and keep failures non-blocking for trading, reconciliation, and audit flows.

## Operational Guidance

- Keep credentials in `.env.prod`, not GitHub.
- Rotate webhook and bot tokens if they are exposed.
- Prefer private channels or restricted recipients.
- Treat alert destinations as sensitive because alert content can reveal operational state.
- Test each destination with a synthetic operational alert before relying on it.
