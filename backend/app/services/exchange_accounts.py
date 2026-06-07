from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import ApiKeySecret, ExchangeAccount


def list_accounts(db: Session, *, user_id: str) -> list[ExchangeAccount]:
    return list(db.scalars(select(ExchangeAccount).where(ExchangeAccount.user_id == user_id)))


def create_account(db: Session, *, user_id: str, data: dict[str, object]) -> ExchangeAccount:
    account = ExchangeAccount(user_id=user_id, **data)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_owned_account(db: Session, *, user_id: str, account_id: str) -> ExchangeAccount | None:
    return db.scalar(
        select(ExchangeAccount).where(
            ExchangeAccount.id == account_id,
            ExchangeAccount.user_id == user_id,
        )
    )


def update_account(account: ExchangeAccount, data: dict[str, object], db: Session) -> ExchangeAccount:
    for key, value in data.items():
        if value is not None:
            setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


def delete_account(account: ExchangeAccount, db: Session) -> None:
    account.is_active = False
    account.trading_enabled = False
    db.commit()


def upsert_api_key_secret(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    api_key: str,
    api_secret: str,
    passphrase: str | None,
) -> ApiKeySecret:
    secret = db.scalar(
        select(ApiKeySecret).where(ApiKeySecret.exchange_account_id == exchange_account_id)
    )
    encrypted_passphrase = encrypt_secret(passphrase) if passphrase else None
    if secret is None:
        secret = ApiKeySecret(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            encrypted_api_key=encrypt_secret(api_key),
            encrypted_api_secret=encrypt_secret(api_secret),
            encrypted_passphrase=encrypted_passphrase,
        )
        db.add(secret)
    else:
        secret.encrypted_api_key = encrypt_secret(api_key)
        secret.encrypted_api_secret = encrypt_secret(api_secret)
        secret.encrypted_passphrase = encrypted_passphrase
    db.commit()
    db.refresh(secret)
    return secret


def get_api_key_secret_metadata(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
) -> ApiKeySecret | None:
    return db.scalar(
        select(ApiKeySecret).where(
            ApiKeySecret.user_id == user_id,
            ApiKeySecret.exchange_account_id == exchange_account_id,
        )
    )


def delete_api_key_secret(secret: ApiKeySecret, db: Session) -> None:
    db.delete(secret)
    db.commit()
