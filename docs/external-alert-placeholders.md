# External Alert Placeholders

This step adds configuration boundaries for future Telegram, email, and webhook alert delivery. The default state is disabled and no real alert is sent by this step.

## Supported Placeholder Channels

- Telegram
- Email through SMTP
- Webhook

## Environment Variables

All channels are disabled by default:

```bash
TELEGRAM_ALERTS_ENABLED=false
EMAIL_ALERTS_ENABLED=false
WEBHOOK_ALERTS_ENABLED=false
```

Telegram placeholders:

```bash
TELEGRAM_BOT_TOKEN=replace-with-telegram-bot-token
TELEGRAM_CHAT_ID=replace-with-telegram-chat-id
```

Email placeholders:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=replace-with-smtp-password
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=ops@example.com
```

Webhook placeholders:

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

External alerts should use coarse operational messages such as:

- service unhealthy
- reconciliation drift detected by severity
- rate-limit protection triggered
- emergency stop enabled
- backup failed

## Current Implementation

`app.services.external_alerts` only builds a validated alert channel plan and returns a redacted summary. It does not perform network requests. Real sending should be implemented in a later step with strict tests for redaction, retry behavior, and failure isolation.

## Operational Guidance

- Keep credentials in `.env.prod`, not GitHub.
- Rotate webhook and bot tokens if they are exposed.
- Prefer private channels or restricted recipients.
- Treat alert destinations as sensitive because alert content can reveal operational state.
