import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountMode,
    ExchangeAccount,
    ExchangeName,
    InternalNotification,
    NotificationChannel,
    NotificationPreference,
    User,
)
from app.services.notification_service import (
    ExternalNotificationChannelDisabledError,
    ExternalNotificationPreferenceDisabledError,
    InternalNotificationInput,
    NotificationEventType,
    NotificationPreferenceUpdate,
    NotificationService,
    SensitiveNotificationPayloadError,
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


def create_second_user_and_account(db_session: Session) -> tuple[User, ExchangeAccount]:
    user = User(
        email="notify-other@example.com",
        username="notify-other-user",
        password_hash="hashed-password",
    )
    db_session.add(user)
    db_session.flush()
    account = ExchangeAccount(
        user_id=user.id,
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.TESTNET,
        account_label="other testnet mock",
    )
    db_session.add(account)
    db_session.flush()
    return user, account


def create_notification(
    db_session: Session,
    service: NotificationService,
    *,
    user: User,
    account: ExchangeAccount,
    title: str,
) -> InternalNotification:
    return service.create_internal_notification(
        db_session,
        InternalNotificationInput(
            user_id=user.id,
            exchange_account_id=account.id,
            severity="WARNING",
            title=title,
            message="Position reconciliation detected one drifted symbol.",
            payload={"symbol": "BTCUSDT", "difference_count": 1},
        ),
    )


def drift_notification_input(user: User, account: ExchangeAccount) -> InternalNotificationInput:
    return InternalNotificationInput(
        user_id=user.id,
        exchange_account_id=account.id,
        severity="WARNING",
        title="Position drift detected",
        message="Position reconciliation detected one drifted symbol.",
        payload={"symbol": "BTCUSDT", "difference_count": 1},
        event_type=NotificationEventType.POSITION_DRIFT,
    )


def test_create_internal_notification_persists_unread_record(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    record = create_notification(
        db_session,
        service,
        user=user,
        account=account,
        title="Position drift detected",
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


def test_list_internal_notifications_is_scoped_by_user_id(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    other_user, other_account = create_second_user_and_account(db_session)
    service = NotificationService()
    own_notification = create_notification(
        db_session,
        service,
        user=user,
        account=account,
        title="Own drift",
    )
    create_notification(
        db_session,
        service,
        user=other_user,
        account=other_account,
        title="Other drift",
    )

    notifications = service.list_internal_notifications(db_session, user_id=user.id)

    assert notifications == (own_notification,)


def test_list_internal_notifications_can_filter_unread(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()
    read_notification = create_notification(
        db_session,
        service,
        user=user,
        account=account,
        title="Read drift",
    )
    unread_notification = create_notification(
        db_session,
        service,
        user=user,
        account=account,
        title="Unread drift",
    )
    service.mark_internal_notification_read(
        db_session,
        user_id=user.id,
        notification_id=read_notification.id,
    )

    notifications = service.list_internal_notifications(
        db_session,
        user_id=user.id,
        unread_only=True,
    )

    assert notifications == (unread_notification,)


def test_mark_internal_notification_read_is_scoped_by_user_id(db_session: Session) -> None:
    user, _account = create_user_and_account(db_session)
    other_user, other_account = create_second_user_and_account(db_session)
    service = NotificationService()
    other_notification = create_notification(
        db_session,
        service,
        user=other_user,
        account=other_account,
        title="Other drift",
    )

    result = service.mark_internal_notification_read(
        db_session,
        user_id=user.id,
        notification_id=other_notification.id,
    )

    assert result is None
    assert other_notification.is_read is False
    assert other_notification.read_at is None


def test_mark_internal_notification_read_sets_read_timestamp(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()
    notification = create_notification(
        db_session,
        service,
        user=user,
        account=account,
        title="Own drift",
    )

    result = service.mark_internal_notification_read(
        db_session,
        user_id=user.id,
        notification_id=notification.id,
    )

    assert result == notification
    assert notification.is_read is True
    assert notification.read_at is not None


def test_get_or_create_preferences_defaults_to_internal_only(db_session: Session) -> None:
    user, _account = create_user_and_account(db_session)
    service = NotificationService()

    preferences = service.get_or_create_preferences(db_session, user_id=user.id)

    assert preferences.user_id == user.id
    assert preferences.internal_enabled is True
    assert preferences.telegram_enabled is False
    assert preferences.email_enabled is False
    assert preferences.webhook_enabled is False
    assert preferences.position_drift_enabled is True
    assert preferences.risk_rejection_enabled is True
    assert preferences.order_failure_enabled is True


def test_get_or_create_preferences_is_scoped_by_user_id(db_session: Session) -> None:
    user, _account = create_user_and_account(db_session)
    other_user, _other_account = create_second_user_and_account(db_session)
    service = NotificationService()

    own_preferences = service.get_or_create_preferences(db_session, user_id=user.id)
    other_preferences = service.get_or_create_preferences(db_session, user_id=other_user.id)

    stored = db_session.scalars(select(NotificationPreference)).all()
    assert own_preferences.user_id == user.id
    assert other_preferences.user_id == other_user.id
    assert {preference.user_id for preference in stored} == {user.id, other_user.id}


def test_update_preferences_updates_internal_and_event_toggles(db_session: Session) -> None:
    user, _account = create_user_and_account(db_session)
    service = NotificationService()

    preferences = service.update_preferences(
        db_session,
        user_id=user.id,
        update=NotificationPreferenceUpdate(
            internal_enabled=False,
            position_drift_enabled=False,
            risk_rejection_enabled=False,
        ),
    )

    assert preferences.internal_enabled is False
    assert preferences.position_drift_enabled is False
    assert preferences.risk_rejection_enabled is False
    assert preferences.order_failure_enabled is True
    assert preferences.telegram_enabled is False
    assert preferences.email_enabled is False
    assert preferences.webhook_enabled is False


def test_update_preferences_rejects_external_delivery_enablement(
    db_session: Session,
) -> None:
    user, _account = create_user_and_account(db_session)
    service = NotificationService()

    with pytest.raises(ExternalNotificationPreferenceDisabledError) as exc_info:
        service.update_preferences(
            db_session,
            user_id=user.id,
            update=NotificationPreferenceUpdate(email_enabled=True),
        )

    assert exc_info.value.channel == NotificationChannel.EMAIL
    assert db_session.scalars(select(NotificationPreference)).all() == []


def test_preference_aware_creation_writes_when_enabled(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()

    record = service.create_preference_aware_internal_notification(
        db_session,
        drift_notification_input(user, account),
    )

    stored = db_session.scalars(select(InternalNotification)).one()
    assert record == stored
    assert stored.user_id == user.id


def test_preference_aware_creation_respects_global_internal_toggle(
    db_session: Session,
) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()
    service.update_preferences(
        db_session,
        user_id=user.id,
        update=NotificationPreferenceUpdate(internal_enabled=False),
    )

    record = service.create_preference_aware_internal_notification(
        db_session,
        drift_notification_input(user, account),
    )

    assert record is None
    assert db_session.scalars(select(InternalNotification)).all() == []


def test_preference_aware_creation_respects_event_toggle(db_session: Session) -> None:
    user, account = create_user_and_account(db_session)
    service = NotificationService()
    service.update_preferences(
        db_session,
        user_id=user.id,
        update=NotificationPreferenceUpdate(position_drift_enabled=False),
    )

    record = service.create_preference_aware_internal_notification(
        db_session,
        drift_notification_input(user, account),
    )

    assert record is None
    assert db_session.scalars(select(InternalNotification)).all() == []
