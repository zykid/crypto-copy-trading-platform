from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session
from test_testnet_order_lifecycle import _submitted_execution

from app.core.encryption import encrypt_secret
from app.db.models.exchange_account import ApiKeySecret, ExchangeName
from app.db.models.observability import AuditLog
from app.db.models.trading import OrderExecutionStatus
from app.exchanges.http_client import PreparedExchangeRequest
from app.services.testnet_user_stream_service import (
    TestnetUserStreamBlockedError,
    consume_bounded_testnet_user_stream,
)
from app.services.testnet_websocket_transport import TestnetWebSocketTransportError


@dataclass
class FakeHttpClient:
    prepared: PreparedExchangeRequest | None = None

    def execute_prepared_request(
        self,
        prepared: PreparedExchangeRequest,
    ) -> dict[str, object]:
        self.prepared = prepared
        return {"listenKey": "test-listen-key"}


class FakeTransport:
    def __init__(self) -> None:
        self.connected_url: str | None = None
        self.closed = False
        self._received = False

    def connect(self, websocket_url: str) -> None:
        self.connected_url = websocket_url

    def send_json(self, payload: dict[str, object]) -> None:
        raise AssertionError("Binance user stream must not send a websocket login payload")

    def receive_json(self) -> dict[str, object]:
        if self._received:
            raise TestnetWebSocketTransportError()
        self._received = True
        return {
            "e": "executionReport",
            "c": "testnet-lifecycle-client",
            "i": 901,
            "X": "FILLED",
            "z": "0.01",
        }

    def close(self) -> None:
        self.closed = True


def test_bounded_user_stream_consumption_persists_order_update_and_audit(
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
    transport = FakeTransport()

    result = consume_bounded_testnet_user_stream(
        db_session,
        user_id=user_id,
        exchange_account_id=account_id,
        testnet_adapters_enabled=True,
        max_messages=1,
        transport_factory=lambda exchange_name: transport,
        http_client=FakeHttpClient(),
    )

    db_session.refresh(execution)
    audit = db_session.query(AuditLog).one()
    assert result.status == "MESSAGE_LIMIT_REACHED"
    assert result.messages_processed == 1
    assert execution.status == OrderExecutionStatus.FILLED
    assert transport.connected_url == "wss://stream.testnet.binance.vision/ws/test-listen-key"
    assert transport.closed is True
    assert audit.action == "testnet.user_stream.consume.completed"
    assert audit.payload["exchange_name"] == ExchangeName.BINANCE.value


def test_bounded_user_stream_requires_explicit_testnet_enablement(
    db_session: Session,
) -> None:
    user_id, account_id, _ = _submitted_execution(db_session)

    with pytest.raises(TestnetUserStreamBlockedError, match="explicitly enabled"):
        consume_bounded_testnet_user_stream(
            db_session,
            user_id=user_id,
            exchange_account_id=account_id,
            testnet_adapters_enabled=False,
            max_messages=1,
        )
