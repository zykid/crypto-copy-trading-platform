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
from app.services.real_open_orders import (
    RealOpenOrdersAuthenticationError,
    RealOpenOrdersBlockedError,
    read_real_open_orders,
)
from app.services.users import create_user


class FakeOpenOrdersClient:
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
                    "ordId": "12345",
                    "instId": "BTC-USDT",
                    "side": "buy",
                    "ordType": "limit",
                    "state": "live",
                    "px": "80000",
                    "sz": "0.0001",
                    "accFillSz": "0",
                    "cTime": "1710000000000",
                    "apiKey": credentials.api_key,
                }
            ]
        }


class FailingOpenOrdersClient(FakeOpenOrdersClient):
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
        email="orders-owner@example.com",
        username="orders-owner",
        password="very-strong-password",
    )
    account = create_account(
        db,
        user_id=user.id,
        data={
            "exchange_name": ExchangeName.OKX,
            "account_label": "OKX orders read-only",
            "account_mode": AccountMode.REAL,
            "trading_enabled": trading_enabled,
        },
    )
    upsert_api_key_secret(
        db,
        user_id=user.id,
        exchange_account_id=account.id,
        api_key="orders-api-key",
        api_secret="orders-api-secret",
        passphrase="orders-passphrase",
    )
    return user, account


def test_real_open_orders_reads_sanitized_okx_orders(db_session: Session) -> None:
    user, account = _create_real_account(db_session)
    client = FakeOpenOrdersClient()

    result = read_real_open_orders(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        http_client=client,
    )

    assert result.orders == (
        {
            "exchange": "okx",
            "order_id": "12345",
            "symbol": "BTC-USDT",
            "side": "buy",
            "order_type": "limit",
            "status": "live",
            "price": "80000",
            "quantity": "0.0001",
            "filled_quantity": "0",
            "created_at": "1710000000000",
        },
    )
    assert client.calls == [
        ("/api/v5/trade/orders-pending", {"instType": "SPOT"}, ExchangeSecurityType.SIGNED)
    ]
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "real.read_only.open_orders.loaded")
    )
    assert audit is not None
    assert audit.payload["order_count"] == 1
    assert "orders-api-key" not in str(audit.payload)


def test_real_open_orders_blocks_trading_enabled_account(db_session: Session) -> None:
    user, account = _create_real_account(db_session, trading_enabled=True)

    with pytest.raises(RealOpenOrdersBlockedError, match="blocked") as error:
        read_real_open_orders(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FakeOpenOrdersClient(),
        )

    assert "trading must remain disabled" in " ".join(error.value.reasons)


def test_real_open_orders_keeps_exchange_failure_metadata_safe(db_session: Session) -> None:
    user, account = _create_real_account(db_session)

    with pytest.raises(RealOpenOrdersAuthenticationError) as error:
        read_real_open_orders(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FailingOpenOrdersClient(),
        )

    assert error.value.failure_type == "authentication_failed"
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "real.read_only.open_orders.loaded")
    )
    assert audit is not None
    assert audit.payload["failure_type"] == "authentication_failed"
    assert "orders-api-key" not in str(audit.payload)
