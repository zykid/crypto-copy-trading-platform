import json
from collections.abc import Callable
from typing import Any, Protocol

from websocket import WebSocketException, create_connection

from app.db.models.exchange_account import ExchangeName
from app.exchanges.testnet_config import get_testnet_endpoint_config


class TestnetWebSocketTransportError(RuntimeError):
    def __init__(self, message: str = "testnet WebSocket transport failed") -> None:
        super().__init__(message)


class WebSocketConnection(Protocol):
    def settimeout(self, timeout: float) -> None: ...

    def send(self, payload: str) -> int: ...

    def recv(self) -> str | bytes: ...

    def close(self) -> None: ...


WebSocketConnectionFactory = Callable[..., WebSocketConnection]


class TestnetWebSocketTransport:
    def __init__(
        self,
        *,
        exchange_name: ExchangeName,
        connection_factory: WebSocketConnectionFactory = create_connection,
        connect_timeout_seconds: float = 10.0,
        receive_timeout_seconds: float = 30.0,
        max_message_bytes: int = 1_048_576,
    ) -> None:
        self._exchange_name = exchange_name
        self._connection_factory = connection_factory
        self._connect_timeout_seconds = connect_timeout_seconds
        self._receive_timeout_seconds = receive_timeout_seconds
        self._max_message_bytes = max_message_bytes
        self._connection: WebSocketConnection | None = None

    def connect(self, websocket_url: str) -> None:
        if self._connection is not None:
            raise TestnetWebSocketTransportError("testnet WebSocket is already connected")
        if not _is_allowed_testnet_websocket_url(
            exchange_name=self._exchange_name,
            websocket_url=websocket_url,
        ):
            raise TestnetWebSocketTransportError("testnet WebSocket endpoint is not allowed")

        try:
            connection = self._connection_factory(
                websocket_url,
                timeout=self._connect_timeout_seconds,
                enable_multithread=True,
            )
            connection.settimeout(self._receive_timeout_seconds)
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise TestnetWebSocketTransportError() from exc
        self._connection = connection

    def send_json(self, payload: dict[str, Any]) -> None:
        connection = self._require_connection()
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        try:
            connection.send(serialized)
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise TestnetWebSocketTransportError() from exc

    def receive_json(self) -> dict[str, Any]:
        connection = self._require_connection()
        try:
            raw_payload = connection.recv()
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise TestnetWebSocketTransportError() from exc

        payload_bytes = (
            raw_payload
            if isinstance(raw_payload, bytes)
            else raw_payload.encode("utf-8")
        )
        if len(payload_bytes) > self._max_message_bytes:
            raise TestnetWebSocketTransportError("testnet WebSocket message is too large")
        try:
            decoded = payload_bytes.decode("utf-8")
            payload = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TestnetWebSocketTransportError(
                "testnet WebSocket message is invalid"
            ) from exc
        if not isinstance(payload, dict):
            raise TestnetWebSocketTransportError(
                "testnet WebSocket message must be a JSON object"
            )
        return payload

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        try:
            connection.close()
        except (OSError, WebSocketException) as exc:
            raise TestnetWebSocketTransportError() from exc

    def _require_connection(self) -> WebSocketConnection:
        if self._connection is None:
            raise TestnetWebSocketTransportError("testnet WebSocket is not connected")
        return self._connection


def _is_allowed_testnet_websocket_url(
    *,
    exchange_name: ExchangeName,
    websocket_url: str,
) -> bool:
    if not websocket_url.startswith("wss://"):
        return False
    endpoint = get_testnet_endpoint_config(exchange_name)
    if exchange_name == ExchangeName.BINANCE:
        if endpoint.public_ws_url is None:
            return False
        prefix = f"{endpoint.public_ws_url.rstrip('/')}/"
        listen_key = websocket_url.removeprefix(prefix)
        return (
            websocket_url.startswith(prefix)
            and bool(listen_key)
            and "{" not in listen_key
            and "}" not in listen_key
            and "/" not in listen_key
        )
    return endpoint.private_ws_url is not None and websocket_url == endpoint.private_ws_url
