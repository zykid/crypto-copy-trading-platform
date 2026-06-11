from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.observability import (
    InternalNotification,
    NotificationChannel,
    NotificationPreference,
)

SENSITIVE_PAYLOAD_KEY_FRAGMENTS = (
    "api_key",
    "passphrase",
    "password",
    "secret",
    "signature",
    "token",
)
MAX_NOTIFICATION_PAGE_SIZE = 100


class NotificationEventType(StrEnum):
    POSITION_DRIFT = "position_drift"
    RISK_REJECTION = "risk_rejection"
    ORDER_FAILURE = "order_failure"


class NotificationSession(Protocol):
    def add(self, instance: object) -> None: ...

    def flush(self) -> None: ...


class ExternalNotificationChannelDisabledError(RuntimeError):
    def __init__(self, channel: NotificationChannel) -> None:
        super().__init__(f"notification channel {channel.value} is not enabled")
        self.channel = channel


class SensitiveNotificationPayloadError(RuntimeError):
    def __init__(self, key_path: str) -> None:
        super().__init__("notification payload contains a sensitive field")
        self.key_path = key_path


class ExternalNotificationPreferenceDisabledError(RuntimeError):
    def __init__(self, channel: NotificationChannel) -> None:
        super().__init__(f"notification preference for {channel.value} cannot be enabled yet")
        self.channel = channel


@dataclass(frozen=True)
class InternalNotificationInput:
    user_id: str
    exchange_account_id: str | None
    severity: str
    title: str
    message: str
    payload: Mapping[str, object]
    channel: NotificationChannel = NotificationChannel.INTERNAL
    event_type: NotificationEventType | None = None


@dataclass(frozen=True)
class NotificationPreferenceUpdate:
    internal_enabled: bool | None = None
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None
    webhook_enabled: bool | None = None
    position_drift_enabled: bool | None = None
    risk_rejection_enabled: bool | None = None
    order_failure_enabled: bool | None = None


class NotificationService:
    def create_internal_notification(
        self,
        db: NotificationSession,
        notification: InternalNotificationInput,
    ) -> InternalNotification:
        if notification.channel != NotificationChannel.INTERNAL:
            raise ExternalNotificationChannelDisabledError(notification.channel)

        payload = _safe_payload(notification.payload)
        record = InternalNotification(
            user_id=notification.user_id,
            exchange_account_id=notification.exchange_account_id,
            channel=NotificationChannel.INTERNAL.value,
            severity=notification.severity,
            title=notification.title,
            message=notification.message,
            payload=payload,
        )
        db.add(record)
        db.flush()
        return record

    def create_internal_notifications(
        self,
        db: NotificationSession,
        notifications: Iterable[InternalNotificationInput],
    ) -> tuple[InternalNotification, ...]:
        return tuple(
            self.create_internal_notification(db, notification)
            for notification in notifications
            if notification.channel == NotificationChannel.INTERNAL
        )

    def create_preference_aware_internal_notification(
        self,
        db: Session,
        notification: InternalNotificationInput,
    ) -> InternalNotification | None:
        if notification.channel != NotificationChannel.INTERNAL:
            raise ExternalNotificationChannelDisabledError(notification.channel)

        preferences = self.get_or_create_preferences(db, user_id=notification.user_id)
        if not _preferences_allow_internal_notification(preferences, notification.event_type):
            return None
        return self.create_internal_notification(db, notification)

    def create_preference_aware_internal_notifications(
        self,
        db: Session,
        notifications: Iterable[InternalNotificationInput],
    ) -> tuple[InternalNotification, ...]:
        records: list[InternalNotification] = []
        for notification in notifications:
            if notification.channel != NotificationChannel.INTERNAL:
                continue
            record = self.create_preference_aware_internal_notification(db, notification)
            if record is not None:
                records.append(record)
        return tuple(records)

    def list_internal_notifications(
        self,
        db: Session,
        *,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> tuple[InternalNotification, ...]:
        bounded_limit = min(max(limit, 1), MAX_NOTIFICATION_PAGE_SIZE)
        query = select(InternalNotification).where(InternalNotification.user_id == user_id)
        if unread_only:
            query = query.where(InternalNotification.is_read.is_(False))
        query = query.order_by(
            InternalNotification.created_at.desc(),
            InternalNotification.id.desc(),
        ).limit(bounded_limit)
        return tuple(db.scalars(query).all())

    def get_owned_internal_notification(
        self,
        db: Session,
        *,
        user_id: str,
        notification_id: str,
    ) -> InternalNotification | None:
        return db.scalar(
            select(InternalNotification).where(
                InternalNotification.id == notification_id,
                InternalNotification.user_id == user_id,
            )
        )

    def mark_internal_notification_read(
        self,
        db: Session,
        *,
        user_id: str,
        notification_id: str,
    ) -> InternalNotification | None:
        notification = self.get_owned_internal_notification(
            db,
            user_id=user_id,
            notification_id=notification_id,
        )
        if notification is None:
            return None
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            db.flush()
        return notification

    def get_or_create_preferences(
        self,
        db: Session,
        *,
        user_id: str,
    ) -> NotificationPreference:
        preferences = db.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        if preferences is not None:
            return preferences

        preferences = NotificationPreference(user_id=user_id)
        db.add(preferences)
        db.flush()
        return preferences

    def update_preferences(
        self,
        db: Session,
        *,
        user_id: str,
        update: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        _reject_external_delivery_enablement(update)
        preferences = self.get_or_create_preferences(db, user_id=user_id)
        for field_name, value in update.__dict__.items():
            if value is not None:
                setattr(preferences, field_name, value)
        db.flush()
        return preferences


def _reject_external_delivery_enablement(update: NotificationPreferenceUpdate) -> None:
    blocked_fields = (
        ("telegram_enabled", NotificationChannel.TELEGRAM),
        ("email_enabled", NotificationChannel.EMAIL),
        ("webhook_enabled", NotificationChannel.WEBHOOK),
    )
    for field_name, channel in blocked_fields:
        if getattr(update, field_name) is True:
            raise ExternalNotificationPreferenceDisabledError(channel)


def _preferences_allow_internal_notification(
    preferences: NotificationPreference,
    event_type: NotificationEventType | None,
) -> bool:
    if not preferences.internal_enabled:
        return False
    event_toggles = {
        NotificationEventType.POSITION_DRIFT: preferences.position_drift_enabled,
        NotificationEventType.RISK_REJECTION: preferences.risk_rejection_enabled,
        NotificationEventType.ORDER_FAILURE: preferences.order_failure_enabled,
    }
    if event_type is None:
        return True
    return event_toggles[event_type]


def _safe_payload(payload: Mapping[str, object]) -> dict[str, object]:
    return _copy_safe_mapping(payload, key_path=())


def _copy_safe_mapping(
    payload: Mapping[str, object],
    *,
    key_path: tuple[str, ...],
) -> dict[str, object]:
    safe_payload: dict[str, object] = {}
    for key, value in payload.items():
        key_text = str(key)
        _raise_if_sensitive_key(key_text, key_path=key_path)
        safe_payload[key_text] = _copy_safe_value(value, key_path=(*key_path, key_text))
    return safe_payload


def _copy_safe_value(value: object, *, key_path: tuple[str, ...]) -> object:
    if isinstance(value, Mapping):
        return _copy_safe_mapping(value, key_path=key_path)
    if isinstance(value, tuple | list):
        return [_copy_safe_value(item, key_path=key_path) for item in value]
    return value


def _raise_if_sensitive_key(key: str, *, key_path: tuple[str, ...]) -> None:
    normalized_key = key.lower()
    if any(fragment in normalized_key for fragment in SENSITIVE_PAYLOAD_KEY_FRAGMENTS):
        full_path = ".".join((*key_path, key))
        raise SensitiveNotificationPayloadError(full_path)


notification_service = NotificationService()