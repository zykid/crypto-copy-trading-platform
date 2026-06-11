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
- Tenant-scoped internal notification listing through `/api/v1/notifications`.
- Tenant-scoped unread filtering and read-state updates.
- Tenant-scoped notification preference storage through `NotificationPreference`.
- Current-user notification preference read/update APIs.
- Explicit rejection when a user attempts to enable Telegram, Email, or Webhook delivery.

Not implemented yet:

- Telegram delivery.
- Email delivery.
- Webhook delivery.
- Retry queues for external delivery.
- External delivery credentials or destination configuration.

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

Notification reads and read-state updates are always scoped by the authenticated user's `user_id`. The API does not accept a frontend-supplied `user_id`, and an attempt to read or mark another user's notification returns the same not-found behavior as a missing notification.

Notification preferences are also scoped by the authenticated user's `user_id`. The API can disable internal notification or event-category toggles for the current user, but external delivery toggles cannot be enabled until the dedicated delivery adapters, destination validation, and delivery audit records exist.

## Current Use

Position reconciliation drift alerts can now create internal notifications through the shared service. Matched reconciliation reports still write audit records only and do not create notifications.

Users can list their internal notifications, mark their own notifications as read, and manage current-user notification preferences. This is intentionally internal-only and does not deliver Telegram, Email, or Webhook messages.

## Next Boundaries

Future steps can add:

- Admin-only system notification views.
- External delivery adapters with explicit opt-in configuration.
- Delivery audit records and retry state.
- Notification preference integration into notification creation decisions.

External delivery must remain disabled by default.
