from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials
from app.services.testnet_user_stream import build_testnet_user_stream_connection_plan
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamConnectionStatus,
    TestnetUserStreamEventType,
    TestnetUserStreamRuntime,
    parse_testnet_user_stream_event,
)


class RecordingSocketClient:
    def __init__(self) -> None:
        self.connected_url: str | None = None
        self.sent_messages: list[dict[str, Any]] = []
        self.closed = False

    def connect(self, websocket_url: str) -> None:
        self.connected_url = websocket_url

    def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_messages.append(payload)

    def close(self) -> None:
        self.closed = True


class FailingSocketClient(RecordingSocketClient):
    def connect(self, websocket_url: str) -> None:
        raise RuntimeError("socket unavailable")


def credentials() -> ExchangeCredentials:
    return ExchangeCredentials(
        api_key="test-api-key",
        api_secret="test-api-secret",
        passphrase="test-passphrase",
    )


def test_runtime_opens_authenticated_bybit_session_with_injected_socket_client() -> None:
    socket_client = RecordingSocketClient()
    runtime = TestnetUserStreamRuntime(socket_client=socket_client)
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-1",
        exchange_name=ExchangeName.BYBIT,
        credentials=credentials(),
    )

    session = runtime.open_session(plan)

    assert session.status == TestnetUserStreamConnectionStatus.AUTHENTICATED
    assert socket_client.connected_url == "wss://stream-testnet.bybit.com/v5/private"
    assert len(socket_client.sent_messages) == 1
    assert socket_client.sent_messages[0]["op"] == "auth"
    assert "test-api-secret" not in str(socket_client.sent_messages[0])


def test_runtime_opens_binance_session_without_websocket_login_message() -> None:
    socket_client = RecordingSocketClient()
    runtime = TestnetUserStreamRuntime(socket_client=socket_client)
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-2",
        exchange_name=ExchangeName.BINANCE,
        credentials=credentials(),
    )

    session = runtime.open_session(plan)

    assert session.status == TestnetUserStreamConnectionStatus.CONNECTED
    assert socket_client.connected_url == "wss://stream.testnet.binance.vision/ws/{listenKey}"
    assert socket_client.sent_messages == []


def test_runtime_returns_failed_session_when_socket_client_fails() -> None:
    runtime = TestnetUserStreamRuntime(socket_client=FailingSocketClient())
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-3",
        exchange_name=ExchangeName.OKX,
        credentials=credentials(),
    )

    session = runtime.open_session(plan)

    assert session.status == TestnetUserStreamConnectionStatus.FAILED


def test_runtime_closes_session_with_injected_socket_client() -> None:
    socket_client = RecordingSocketClient()
    runtime = TestnetUserStreamRuntime(socket_client=socket_client)
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-4",
        exchange_name=ExchangeName.BYBIT,
        credentials=credentials(),
    )
    session = runtime.open_session(plan)

    closed = runtime.close_session(session)

    assert closed.status == TestnetUserStreamConnectionStatus.CLOSED
    assert socket_client.closed is True


def test_parse_binance_user_stream_order_and_balance_events() -> None:
    order = parse_testnet_user_stream_event(
        exchange_name=ExchangeName.BINANCE,
        payload={"e": "executionReport", "s": "BTCUSDT"},
    )
    balance = parse_testnet_user_stream_event(
        exchange_name=ExchangeName.BINANCE,
        payload={"e": "outboundAccountPosition"},
    )

    assert order.event_type == TestnetUserStreamEventType.ORDER
    assert balance.event_type == TestnetUserStreamEventType.BALANCE


def test_parse_bybit_user_stream_event_types() -> None:
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BYBIT,
            payload={"topic": "order"},
        ).event_type
        == TestnetUserStreamEventType.ORDER
    )
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BYBIT,
            payload={"topic": "wallet"},
        ).event_type
        == TestnetUserStreamEventType.BALANCE
    )
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.BYBIT,
            payload={"topic": "position"},
        ).event_type
        == TestnetUserStreamEventType.POSITION
    )


def test_parse_okx_user_stream_event_types() -> None:
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.OKX,
            payload={"arg": {"channel": "orders"}},
        ).event_type
        == TestnetUserStreamEventType.ORDER
    )
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.OKX,
            payload={"arg": {"channel": "account"}},
        ).event_type
        == TestnetUserStreamEventType.BALANCE
    )
    assert (
        parse_testnet_user_stream_event(
            exchange_name=ExchangeName.OKX,
            payload={"arg": {"channel": "positions"}},
        ).event_type
        == TestnetUserStreamEventType.POSITION
    )


def test_unknown_user_stream_event_stays_unknown() -> None:
    event = parse_testnet_user_stream_event(
        exchange_name=ExchangeName.BINANCE,
        payload={"e": "unknown"},
    )

    assert event.event_type == TestnetUserStreamEventType.UNKNOWN
