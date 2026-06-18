from typing import Any

import pytest
from websocket import WebSocketException

from app.db.models.exchange_account import ExchangeName
from app.services.testnet_websocket_transport import (
    TestnetWebSocketTransport as WebSocketTransport,
)
from app.services.testnet_websocket_transport import (
    WebSocketTransportError as WebSocketTransportError,
)


class FakeConnection:
    def __init__(self, messages: list[str | bytes] | None = None) -> None:
        self.messages = list(messages or [])
        self.timeout: float | None = None
        self.sent_payloads: list[str] = []
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def send(self, payload: str) -> int:
        self.sent_payloads.append(payload)
        return len(payload)

    def recv(self) -> str | bytes:
        return self.messages.pop(0)

    def close(self) -> None:
        self.closed = True


class RecordingConnectionFactory:
    def __init__(
        self,
        connection: FakeConnection | None = None,
        error: Exception | None = None,
    ) -> None:
        self.connection = connection or FakeConnection()
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, **kwargs: Any) -> FakeConnection:
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.connection


def test_transport_connects_only_to_configured_bybit_testnet_endpoint() -> None:
    connection = FakeConnection()
    factory = RecordingConnectionFactory(connection)
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BYBIT,
        connection_factory=factory,
        connect_timeout_seconds=4,
        receive_timeout_seconds=9,
    )

    transport.connect("wss://stream-testnet.bybit.com/v5/private")

    assert factory.calls == [
        (
            "wss://stream-testnet.bybit.com/v5/private",
            {"timeout": 4, "enable_multithread": True},
        )
    ]
    assert connection.timeout == 9


def test_transport_rejects_production_endpoint_before_network_connection() -> None:
    factory = RecordingConnectionFactory()
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BYBIT,
        connection_factory=factory,
    )

    with pytest.raises(
        WebSocketTransportError,
        match="testnet WebSocket endpoint is not allowed",
    ):
        transport.connect("wss://stream.bybit.com/v5/private")

    assert factory.calls == []


def test_transport_rejects_unresolved_binance_listen_key_placeholder() -> None:
    factory = RecordingConnectionFactory()
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BINANCE,
        connection_factory=factory,
    )

    with pytest.raises(WebSocketTransportError):
        transport.connect("wss://stream.testnet.binance.vision/ws/{listenKey}")

    assert factory.calls == []


def test_transport_accepts_resolved_binance_testnet_listen_key() -> None:
    factory = RecordingConnectionFactory()
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BINANCE,
        connection_factory=factory,
    )

    transport.connect("wss://stream.testnet.binance.vision/ws/test-listen-key")

    assert len(factory.calls) == 1


def test_transport_sends_and_receives_json_objects() -> None:
    connection = FakeConnection(messages=['{"topic":"order","data":[]}'])
    transport = WebSocketTransport(
        exchange_name=ExchangeName.OKX,
        connection_factory=RecordingConnectionFactory(connection),
    )
    transport.connect("wss://wspap.okx.com:8443/ws/v5/private")

    transport.send_json({"op": "subscribe", "args": [{"channel": "orders"}]})
    received = transport.receive_json()

    assert connection.sent_payloads == [
        '{"op":"subscribe","args":[{"channel":"orders"}]}'
    ]
    assert received == {"topic": "order", "data": []}


def test_transport_rejects_oversized_message() -> None:
    connection = FakeConnection(messages=['{"data":"' + ("x" * 100) + '"}'])
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BYBIT,
        connection_factory=RecordingConnectionFactory(connection),
        max_message_bytes=32,
    )
    transport.connect("wss://stream-testnet.bybit.com/v5/private")

    with pytest.raises(
        WebSocketTransportError,
        match="testnet WebSocket message is too large",
    ):
        transport.receive_json()


def test_transport_rejects_non_object_json_message() -> None:
    connection = FakeConnection(messages=["[]"])
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BYBIT,
        connection_factory=RecordingConnectionFactory(connection),
    )
    transport.connect("wss://stream-testnet.bybit.com/v5/private")

    with pytest.raises(
        WebSocketTransportError,
        match="testnet WebSocket message must be a JSON object",
    ):
        transport.receive_json()


def test_transport_wraps_connection_error_without_sensitive_details() -> None:
    factory = RecordingConnectionFactory(
        error=WebSocketException("test-api-secret network detail")
    )
    transport = WebSocketTransport(
        exchange_name=ExchangeName.OKX,
        connection_factory=factory,
    )

    with pytest.raises(WebSocketTransportError) as exc_info:
        transport.connect("wss://wspap.okx.com:8443/ws/v5/private")

    assert str(exc_info.value) == "testnet WebSocket transport failed"
    assert "test-api-secret" not in str(exc_info.value)


def test_transport_close_is_idempotent() -> None:
    connection = FakeConnection()
    transport = WebSocketTransport(
        exchange_name=ExchangeName.BYBIT,
        connection_factory=RecordingConnectionFactory(connection),
    )
    transport.connect("wss://stream-testnet.bybit.com/v5/private")

    transport.close()
    transport.close()

    assert connection.closed is True
