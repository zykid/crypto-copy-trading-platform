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
from app.services.real_read_only_check import (
    RealReadOnlyAuthenticationError,
    RealReadOnlyCheckBlockedError,
    run_real_read_only_check,
)
from app.services.users import create_user


class FakeProductionClient:
    def __init__(self) -> None:
        self.security_types: list[ExchangeSecurityType] = []

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
        self.security_types.append(security_type)
        return {"data": [{"details": []}]}


class FailingProductionClient(FakeProductionClient):
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


def _create_real_account(db: Session, *, user_id: str, trading_enabled: bool = False):
    account = create_account(
        db,
        user_id=user_id,
        data={
            "exchange_name": ExchangeName.OKX,
            "account_label": "OKX production read-only",
            "account_mode": AccountMode.REAL,
            "trading_enabled": trading_enabled,
        },
    )
    upsert_api_key_secret(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
        api_key="production-key",
        api_secret="production-secret",
        passphrase="production-passphrase",
    )
    return account


def test_real_read_only_check_uses_production_okx_security_type(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    account = _create_real_account(db_session, user_id=user.id)
    client = FakeProductionClient()

    result = run_real_read_only_check(
        db_session,
        user_id=user.id,
        exchange_account_id=account.id,
        http_client=client,
    )

    assert result.authenticated is True
    assert client.security_types == [ExchangeSecurityType.SIGNED]
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "real.read_only.authentication.checked"
        )
    )
    assert audit is not None
    assert audit.payload["account_mode"] == "REAL"
    assert "production-key" not in str(audit.payload)


def test_real_read_only_check_blocks_trading_enabled_account(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    account = _create_real_account(
        db_session,
        user_id=user.id,
        trading_enabled=True,
    )

    with pytest.raises(RealReadOnlyCheckBlockedError) as error:
        run_real_read_only_check(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FakeProductionClient(),
        )

    assert "trading must remain disabled" in " ".join(error.value.reasons)


def test_real_read_only_check_audits_safe_exchange_error_metadata(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        password="very-strong-password",
    )
    account = _create_real_account(db_session, user_id=user.id)

    with pytest.raises(RealReadOnlyAuthenticationError) as error:
        run_real_read_only_check(
            db_session,
            user_id=user.id,
            exchange_account_id=account.id,
            http_client=FailingProductionClient(),
        )

    assert error.value.failure_type == "authentication_failed"
    assert error.value.exchange_code == "50111"
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "real.read_only.authentication.checked"
        )
    )
    assert audit is not None
    assert audit.payload["failure_type"] == "authentication_failed"
    assert audit.payload["exchange_code"] == "50111"
    assert "production-key" not in str(audit.payload)
