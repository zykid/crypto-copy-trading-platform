import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    ExchangeAccount,
    ExchangeName,
    InternalNotification,
    NotificationChannel,
    User,
)
from app.services.notification_service import (
    ExternalNotificationChannelDisabledError,
    InternalNotificationInput,
    SensitiveNotificationPayloadError,
    NotificationService,
)


def create_user_and_account(db_session: Session) -> tuple[User, ExchangeAccount]:
    user = User(
        email="notify@example.com",
        username="notify-user",
        password_hash="hashed-password",
    )
    db_session.add(user)
    db_session.flush()
    account = ExchangeAccount(
        user_id=user.id,
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.TESTNET,
        account_label="testnet mock",
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def test_create_internal_notification_persists_unread_record(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    record = service.create_internal_notification(
        db_session,
        InternalNotificationInput(
            user_id=user.id,
            exchange_account_id=account.id,
            severity="WARNING",
            title="Position drift detected",
            message="Position reconciliation detected one drifted symbol.",
            payload={"symbol": "BTCUSDT", "difference_count": 1},
        ),
    )

    stored = db_session.scalars(select(InternalNotification)).one()
    assert stored == record
    assert stored.user_id == user.id
    assert stored.exchange_account_id == account.id
    assert stored.channel == NotificationChannel.INTERNAL.value
    assert stored.is_read is False
    assert stored.payload == {"symbol": "BTCUSDT", "difference_count": 1}


def test_create_internal_notifications_skips_external_channels(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    records = service.create_internal_notifications(
        db_session,
        (
            InternalNotificationInput(
                user_id=user.id,
                exchange_account_id=account.id,
                channel=NotificationChannel.INTERNAL,
                severity="CRITICAL",
                title="Internal alert",
                message="Internal alert only.",
                payload={"event_type": "position_reconciliation.drift_detected"},
            ),
            InternalNotificationInput(
                user_id=user.id,
                exchange_account_id=account.id,
                channel=NotificationChannel.EMAIL,
                severity="CRITICAL",
                title="Email alert",
                message="Email channel is reserved for a later phase.",
                payload={"event_type": "position_reconciliation.drift_detected"},
            ),
        ),
    )

    stored = db_session.scalars(select(InternalNotification)).all()
    assert len(records) == 1
    assert stored == [records[0]]
    assert stored[0].channel == NotificationChannel.INTERNAL.value


def test_create_internal_notification_rejects_disabled_external_channel(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    with pytest.raises(ExternalNotificationChannelDisabledError):
        service.create_internal_notification(
            db_session,
            InternalNotificationInput(
                user_id=user.id,
                exchange_account_id=account.id,
                channel=NotificationChannel.WEBHOOK,
                severity="WARNING",
                title="Webhook alert",
                message="Webhook delivery is not enabled.",
                payload={"event_type": "position_reconciliation.drift_detected"},
            ),
        )

    assert db_session.scalars(select(InternalNotification)).all() == []


def test_create_internal_notification_rejects_sensitive_payload_keys(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    with pytest.raises(SensitiveNotificationPayloadError) as exc_info:
        service.create_internal_notification(
            db_session,
            InternalNotificationInput(
                user_id=user.id,
                exchange_account_id=account.id,
                severity="WARNING",
                title="Sensitive alert",
                message="This payload must not be stored.",
                payload={"exchange": {"api_secret": "must-not-store"}},
            ),
        )

    assert exc_info.value.key_path == "exchange.api_secret"
    assert db_session.scalars(select(InternalNotification)).all() == []
