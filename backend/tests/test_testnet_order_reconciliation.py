from dataclasses import dataclass

from sqlalchemy.orm import Session
from test_testnet_order_lifecycle import _submitted_execution

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import ApiKeySecret, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderExecutionStatus
from app.exchanges.http_client import ExchangeHttpRequestError, PreparedExchangeRequest
from app.services.testnet_order_reconciliation import reconcile_pending_testnet_orders


@dataclass
class FakeTransport:
    response: dict[str, object] | Exception
    prepared: PreparedExchangeRequest | None = None

    def request(self, prepared: PreparedExchangeRequest) -> dict[str, object]:
        self.prepared = prepared
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_reconciliation_applies_rest_status_without_submitting_an_order(
    db_session: Session,
) -> None:
    user_id, account_id, execution = _submitted_execution(db_session)
    db_session.add(
        ApiKeySecret(
            user_id=user_id,
            exchange_account_id=account_id,
            encrypted_api_key=encrypt_secret("key"),
            encrypted_api_secret=encrypt_secret("secret"),
        )
    )
    db_session.commit()
    transport = FakeTransport(
        response={
            "clientOrderId": execution.client_order_id,
            "orderId": 99,
            "status": "FILLED",
            "executedQty": "0.01",
        }
    )
    from app.exchanges.http_client import SignedExchangeHttpClient

    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.example",
        transport=transport,
        timestamp_ms_factory=lambda: 1,
    )

    result = reconcile_pending_testnet_orders(
        db_session,
        user_id=user_id,
        exchange_account_id=account_id,
        http_client=client,
    )

    db_session.refresh(execution)
    assert result.attempted == 1
    assert result.transitioned == 1
    assert execution.status == OrderExecutionStatus.FILLED
    assert transport.prepared is not None
    assert transport.prepared.method == "GET"
    assert transport.prepared.path == "/api/v3/order"
    audit = db_session.query(AuditLog).one()
    assert audit.action == "testnet.order.reconciliation.requested"
    assert audit.payload == {
        "exchange_name": "binance",
        "account_mode": "TESTNET",
        "attempted": 1,
        "transitioned": 1,
        "failed": 0,
    }


def test_reconciliation_preserves_pending_status_on_transport_error(
    db_session: Session,
) -> None:
    user_id, account_id, execution = _submitted_execution(db_session)
    db_session.add(
        ApiKeySecret(
            user_id=user_id,
            exchange_account_id=account_id,
            encrypted_api_key=encrypt_secret("key"),
            encrypted_api_secret=encrypt_secret("secret"),
        )
    )
    db_session.commit()
    transport = FakeTransport(
        response=ExchangeHttpRequestError(failure_type="transport_error")
    )
    from app.exchanges.http_client import SignedExchangeHttpClient

    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.example",
        transport=transport,
        timestamp_ms_factory=lambda: 1,
    )

    result = reconcile_pending_testnet_orders(
        db_session,
        user_id=user_id,
        exchange_account_id=account_id,
        http_client=client,
    )

    db_session.refresh(execution)
    assert result.failed == 1
    assert execution.status == OrderExecutionStatus.SUBMITTED
