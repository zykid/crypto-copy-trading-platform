# Phase 3 Internal Notification Service

This step adds the first Notification Service boundary for the testnet preparation phase.

## Scope

Implemented:

- Internal notification persistence through `InternalNotification`.
- A reusable `NotificationService` service layer.
- Filtering so batch notification creation stores only `INTERNAL` notifications.
- Explicit rejection when a single-notification call attempts to use disabled external channels.
- Sensitive payload key detection before notifications are persisted.
- Reconciliation persistence now routes internal alerts through the notification service.

Not implemented yet:

- Telegram delivery.
- Email delivery.
- Webhook delivery.
- Retry queues for external delivery.
- User notification preference APIs.

## Safety Rules

The service does not send external messages in this phase. `TELEGRAM`, `EMAIL`, and `WEBHOOK` remain reserved channels only.

Notification payloads are rejected if any nested key contains sensitive fragments such as:

- `api_key`
- `passphrase`
- `password`
- `secret`
- `signature`
- `token`

This prevents API secrets, signatures, tokens, and credentials from being accidentally written into notification storage.

## Current Use

Position reconciliation drift alerts can now create internal notifications through the shared service. Matched reconciliation reports still write audit records only and do not create notifications.

## Next Boundaries

Future steps can add:

- Read/unread notification API with `user_id` tenant isolation.
- Admin-only system notification views.
- External delivery adapters with explicit opt-in configuration.
- Delivery audit records and retry state.

External delivery must remain disabled by default.
