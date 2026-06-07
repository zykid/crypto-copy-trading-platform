from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.exchange_account import (
    ApiKeySecretMetadata,
    ApiKeySecretUpsert,
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountUpdate,
)
from app.services.exchange_accounts import (
    create_account,
    delete_account,
    delete_api_key_secret,
    get_api_key_secret_metadata,
    get_owned_account,
    list_accounts,
    update_account,
    upsert_api_key_secret,
)

router = APIRouter()


@router.get("", response_model=list[ExchangeAccountResponse])
def read_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_accounts(db, user_id=current_user.id)


@router.post("", response_model=ExchangeAccountResponse, status_code=status.HTTP_201_CREATED)
def add_account(
    payload: ExchangeAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_account(db, user_id=current_user.id, data=payload.model_dump())


@router.get("/{account_id}", response_model=ExchangeAccountResponse)
def read_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return account


@router.patch("/{account_id}", response_model=ExchangeAccountResponse)
def patch_account(
    account_id: str,
    payload: ExchangeAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return update_account(account, payload.model_dump(exclude_unset=True), db)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    delete_account(account, db)


@router.post("/{account_id}/api-key", response_model=ApiKeySecretMetadata)
def set_api_key(
    account_id: str,
    payload: ApiKeySecretUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = upsert_api_key_secret(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
        passphrase=payload.passphrase,
    )
    return ApiKeySecretMetadata(
        exchange_account_id=account.id,
        configured=True,
        has_passphrase=secret.encrypted_passphrase is not None,
    )


@router.get("/{account_id}/api-key", response_model=ApiKeySecretMetadata)
def read_api_key_metadata(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = get_api_key_secret_metadata(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    return ApiKeySecretMetadata(
        exchange_account_id=account.id,
        configured=secret is not None,
        has_passphrase=secret is not None and secret.encrypted_passphrase is not None,
    )


@router.delete("/{account_id}/api-key", status_code=status.HTTP_204_NO_CONTENT)
def remove_api_key(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_owned_account(db, user_id=current_user.id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    secret = get_api_key_secret_metadata(
        db,
        user_id=current_user.id,
        exchange_account_id=account.id,
    )
    if secret is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api key not found")
    delete_api_key_secret(secret, db)
