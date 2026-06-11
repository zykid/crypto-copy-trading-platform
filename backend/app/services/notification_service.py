from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.observability import InternalNotification, NotificationChannel

SENSITIVE_PAYLOAD_KEY_FRAGMENTS = (
    "api_key",
    "passphrase",
    "password",
    "secret",
    "signature",
    "token",
)
MAX_NOTIFICATION_PAGE_SIZE = 100


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


@dataclass(frozen=True)
class InternalNotificationInput:
    user_id: str
    exchange_account_id: str | None
    severity: str
    title: str
    message: str
    payload: Mapping[str, object]
    channel: NotificationChannel = NotificationChannel.INTERNAL


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
        query = query.order_by(InternalNotification.created_at.desc(), InternalNotification.id.desc()).limit(
            bounded_limit
        )
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