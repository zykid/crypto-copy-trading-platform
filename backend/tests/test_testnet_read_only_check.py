from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeSecurityType,
)
from app.services.exchange_accounts import create_account, upsert_api_key_secret
from app.services.testnet_read_only_check import (
    TestnetReadOnlyAccountNotFoundError as ReadOnlyAccountNotFoundError,
    TestnetReadOnlyCheckBlockedError as ReadOnlyCheckBlockedError,
    run_testnet_read_only_check,
)
from app.services.users import create_user


class FakeReadOnlyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ExchangeSecurityType, str]] = []

    def get_public(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise AssertionError("public request is not expected")

    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        self.calls.append((path, security_type, credentials.api_key))
        return {"balances": [{"asset": "USDT", "free": "1", "locked": "0"}]}


def _create_testnet_account(db: Session, *, user_id: str):
    account = create_account(
        db,
        user_id=user_id,
        data={
            "exchange_name": ExchangeName.BINANCE,
            "account_label": "Binance read-only",
            "account_mode": AccountMode.TESTNET,
            "trading_enabled": False,
        },
    )
    upsert_api_key_secret(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        api_key="test-key",
        api_secret="test-secret",
        passphrase=None,
    )
    return account


def test_testnet_read_only_check_authenticates_without_returning_balances(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    account = _create_testnet_account(db_session, user_id=user.id)
    client = FakeReadOnlyClient()

    result = run_testnet_read_only_check(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        testnet_adapters_enabled=True,
        http_client=client,
    )

    assert result.authenticated is True
    assert result.balance_asset_count == 1
    assert client.calls == [
        ("/api/v3/account", ExchangeSecurityType.SIGNED, "test-key")
    ]
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "testnet.read_only.authentication.checked"
        )
    )
    assert audit is not None
    assert audit.payload == {
        "exchange_name": "binance",
        "authenticated": True,
        "balance_asset_count": 1,
    }
    assert "test-key" not in str(audit.payload)
    assert "test-secret" not in str(audit.payload)


def test_testnet_read_only_check_is_blocked_until_explicitly_enabled(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    account = _create_testnet_account(db_session, user_id=user.id)

    with pytest.raises(ReadOnlyCheckBlockedError) as error:
        run_testnet_read_only_check(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            testnet_adapters_enabled=False,
            http_client=FakeReadOnlyClient(),
        )

    assert "testnet adapters must be explicitly enabled" in error.value.reasons


def test_testnet_read_only_check_requires_owned_account(
    db_session: Session,
) -> None:
    owner = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    other = create_user(
        db_session,
        email="other@example.com",
        username="other",
        password="very-strong-password",
    )
    account = _create_testnet_account(db_session, user_id=owner.id)

    with pytest.raises(ReadOnlyAccountNotFoundError, match="account not found"):
        run_testnet_read_only_check(
            db_session,
            user_id=other.id,
            exchange_account_id=account.id,
            testnet_adapters_enabled=True,
            http_client=FakeReadOnlyClient(),
        )
