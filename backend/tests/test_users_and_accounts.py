import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret
from app.core.security import hash_password
from app.db.models.exchange_account import AccountMode, ApiKeySecret, ExchangeName
from app.db.models.user import User
from app.schemas.exchange_account import ApiKeySecretMetadata
from app.services.exchange_accounts import (
    create_account,
    delete_account,
    get_api_key_secret_metadata,
    get_owned_account,
    list_accounts,
    upsert_api_key_secret,
)
from app.services.users import DuplicateUserError, authenticate_user, create_user


def test_user_email_and_username_are_unique(db_session: Session) -> None:
    create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )

    with pytest.raises(DuplicateUserError):
        create_user(
            db_session,
            email="alice@example.com",
            username="alice2",
            password="very-strong-password",
        )


def test_authenticate_user_by_username_or_email(db_session: Session) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )

    username_login = authenticate_user(
        db_session,
        username_or_email="alice",
        password="very-strong-password",
    )
    email_login = authenticate_user(
        db_session,
        username_or_email="alice@example.com",
        password="very-strong-password",
    )

    assert username_login == user
    assert email_login == user
    assert authenticate_user(db_session, username_or_email="alice", password="bad-password") is None


def test_exchange_account_queries_are_scoped_by_user_id(db_session: Session) -> None:
    alice = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    bob = create_user(
        db_session,
        email="bob@example.com",
        username="bob",
        password="very-strong-password",
    )
    alice_account = create_account(
        db_session,
        user_id=alice.id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "alice mock",
            "trading_enabled": False,
        },
    )
    create_account(
        db_session,
        user_id=bob.id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "bob mock",
            "trading_enabled": False,
        },
    )

    alice_accounts = list_accounts(db_session, user_id=alice.id)

    assert [account.user_id for account in alice_accounts] == [alice.id]
    assert get_owned_account(db_session, user_id=bob.id, account_id=alice_account.id) is None


def test_deleted_exchange_accounts_are_hidden_from_user_list(db_session: Session) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    account = create_account(
        db_session,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.MOCK,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "deleted mock",
            "trading_enabled": False,
        },
    )

    delete_account(account, db_session)

    assert list_accounts(db_session, user_id=user.id) == []


def test_api_key_secret_is_encrypted_and_metadata_does_not_expose_plaintext(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    account = create_account(
        db_session,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.BINANCE,
            "account_mode": AccountMode.SIMULATION,
            "account_label": "binance sim",
            "trading_enabled": False,
        },
    )

    secret = upsert_api_key_secret(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        api_key="public-key",
        api_secret="private-secret",
        passphrase="passphrase",
    )

    stored = db_session.scalar(select(ApiKeySecret).where(ApiKeySecret.id == secret.id))
    assert stored is not None
    assert stored.encrypted_api_key != "public-key"
    assert stored.encrypted_api_secret != "private-secret"
    assert decrypt_secret(stored.encrypted_api_secret) == "private-secret"

    metadata_source = get_api_key_secret_metadata(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
    )
    assert metadata_source is not None
    metadata = ApiKeySecretMetadata(
        exchange_account_id=account.id,
        configured=True,
        has_passphrase=metadata_source.encrypted_passphrase is not None,
    )
    serialized = metadata.model_dump()
    assert serialized["configured"] is True
    assert serialized["has_passphrase"] is True
    assert "api_secret" not in serialized
    assert "private-secret" not in str(serialized)


def test_database_unique_constraint_blocks_duplicate_email(db_session: Session) -> None:
    create_user(
        db_session,
        email="alice@example.com",
        username="alice",
        password="very-strong-password",
    )
    db_session.rollback()

    # Service-level duplicate checks are primary; this guards accidental bypasses.
    db_session.add(
        User(
            email="alice@example.com",
            username="alice2",
            password_hash=hash_password("very-strong-password"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
