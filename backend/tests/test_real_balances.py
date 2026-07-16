from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeHttpRequestError,
    ExchangeSecurityType,
)
from app.services.exchange_accounts import create_account, upsert_api_key_secret
from app.services.real_balances import (
    RealBalance,
    RealBalancesAuthenticationError,
    RealBalancesBlockedError,
    read_real_balances,
)
from app.services.users import create_user


class FakeBalancesClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str] | None, ExchangeSecurityType]] = []

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
        self.calls.append((path, params, security_type))
        return {
            "data": [
                {
                    "details": [
                        {
                            "ccy": "USDT",
                            "availBal": "12.5",
                            "frozenBal": "0.5",
                            "cashBal": "13",
                            "apiKey": credentials.api_key,
                        }
                    ]
                }
            ]
        }


class FailingBalancesClient(FakeBalancesClient):
    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        raise ExchangeHttpRequestError(
            failure_type="authentication_failed",
            status_code=401,
            exchange_code="50111",
        )


def _create_real_account(db: Session, *, trading_enabled: bool = False):
    user = create_user(
        db,
        email="balances-owner@example.com",
        username="balances-owner",
        password="very-strong-password",
    )
    account = create_account(
        db,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.OKX,
            "account_label": "OKX balances read-only",
            "account_mode": AccountMode.REAL,
            "trading_enabled": trading_enabled,
        },
    )
    upsert_api_key_secret(
        db,
        user_id=user.id,
        exchange_account_id=account.id,
        api_key="balances-api-key",
        api_secret="balances-api-secret",
        passphrase="balances-passphrase",
    )
    return user, account


def test_real_balances_reads_sanitized_okx_balances(db_session: Session) -> None:
    user, account = _create_real_account(db_session)
    client = FakeBalancesClient()

    result = read_real_balances(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        http_client=client,
    )

    assert result.balances == (
        RealBalance(asset="USDT", free="12.5", locked="0.5", total="13"),
    )
    assert client.calls == [
        ("/api/v5/account/balance", None, ExchangeSecurityType.SIGNED)
    ]
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "real.read_only.balances.loaded")
    )
    assert audit is not None
    assert audit.payload["asset_count"] == 1
    assert "balances-api-key" not in str(audit.payload)
    assert "12.5" not in str(audit.payload)


def test_real_balances_blocks_trading_enabled_account(db_session: Session) -> None:
    user, account = _create_real_account(db_session, trading_enabled=True)

    with pytest.raises(RealBalancesBlockedError, match="blocked") as error:
        read_real_balances(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FakeBalancesClient(),
        )

    assert "trading must remain disabled" in " ".join(error.value.reasons)


def test_real_balances_keeps_exchange_failure_metadata_safe(db_session: Session) -> None:
    user, account = _create_real_account(db_session)

    with pytest.raises(RealBalancesAuthenticationError) as error:
        read_real_balances(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FailingBalancesClient(),
        )

    assert error.value.failure_type == "authentication_failed"
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "real.read_only.balances.loaded")
    )
    assert audit is not None
    assert audit.payload["failure_type"] == "authentication_failed"
    assert "balances-api-key" not in str(audit.payload)
