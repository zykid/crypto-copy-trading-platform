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

The first wired integration point is PostgreSQL backup failure reporting. The backup script sends only a coarse `PostgreSQL backup failed` event with component and error type metadata. Alert delivery errors do not change the backup job's failure code.

The sender is intentionally not wired into trading flows yet. Future integration points must pass only coarse operational events and keep failures non-blocking for trading, reconciliation, and audit flows.

## Operational Guidance

- Keep credentials in `.env.prod`, not GitHub.
- Rotate webhook and bot tokens if they are exposed.
- Prefer private channels or restricted recipients.
- Treat alert destinations as sensitive because alert content can reveal operational state.
- Test each destination with a synthetic operational alert before relying on it.
