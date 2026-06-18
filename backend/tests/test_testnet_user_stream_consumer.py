from dataclasses import dataclass, field
from typing import Any

import pytest

from app.db.models.exchange_account import ExchangeName
from app.services.testnet_user_stream import (
    TestnetUserStreamAuthMethod as UserStreamAuthMethod,
)
from app.services.testnet_user_stream import (
    TestnetUserStreamConnectionPlan as UserStreamConnectionPlan,
)
from app.services.testnet_user_stream_consumer import (
    TestnetUserStreamConsumer as UserStreamConsumer,
)
from app.services.testnet_user_stream_consumer import (
    TestnetUserStreamConsumerStatus as ConsumerStatus,
)
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEvent as UserStreamEvent,
)
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEventType as UserStreamEventType,
)
from app.services.testnet_websocket_transport import (
    TestnetWebSocketTransportError as WebSocketTransportError,
)


@dataclass
class ScriptedTransport:
    receive_items: list[dict[str, Any] | Exception] = field(default_factory=list)
    fail_connect: bool = False
    connected_urls: list[str] = field(default_factory=list)
    sent_messages: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def connect(self, websocket_url: str) -> None:
        if self.fail_connect:
            raise WebSocketTransportError()
        self.connected_urls.append(websocket_url)

    def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_messages.append(payload)

    def receive_json(self) -> dict[str, Any]:
        item = self.receive_items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


class SequenceTransportFactory:
    def __init__(self, transports: list[ScriptedTransport]) -> None:
        self.transports = transports
        self.calls: list[ExchangeName] = []

    def __call__(self, exchange_name: ExchangeName) -> ScriptedTransport:
        self.calls.append(exchange_name)
        return self.transports[len(self.calls) - 1]


def bybit_plan() -> UserStreamConnectionPlan:
    return UserStreamConnectionPlan(
        exchange_account_id="acct-1",
        exchange_name=ExchangeName.BYBIT,
        websocket_url="wss://stream-testnet.bybit.com/v5/private",
        auth_method=UserStreamAuthMethod.BYBIT_AUTH,
        websocket_login_message={"op": "auth", "args": ["key", "expires", "signature"]},
    )


def test_consumer_parses_messages_and_stops_at_explicit_limit() -> None:
    transport = ScriptedTransport(
        receive_items=[
            {"topic": "order", "data": []},
            {"topic": "wallet", "data": []},
        ]
    )
    events: list[UserStreamEvent] = []
    consumer = UserStreamConsumer(
        transport_factory=SequenceTransportFactory([transport]),
        event_handler=events.append,
    )

    result = consumer.consume(bybit_plan(), max_messages=2)

    assert result.status == ConsumerStatus.MESSAGE_LIMIT_REACHED
    assert result.messages_processed == 2
    assert result.reconnect_attempts == 0
    assert [event.event_type for event in events] == [
        UserStreamEventType.ORDER,
        UserStreamEventType.BALANCE,
    ]
    assert transport.closed is True
    assert transport.sent_messages[0]["op"] == "auth"


def test_consumer_reconnects_after_transport_receive_failure() -> None:
    first = ScriptedTransport(
        receive_items=[
            {"topic": "order", "data": []},
            WebSocketTransportError(),
        ]
    )
    second = ScriptedTransport(receive_items=[{"topic": "position", "data": []}])
    factory = SequenceTransportFactory([first, second])
    events: list[UserStreamEvent] = []
    sleeps: list[float] = []
    consumer = UserStreamConsumer(
        transport_factory=factory,
        event_handler=events.append,
        sleeper=sleeps.append,
        max_reconnect_attempts=2,
    )

    result = consumer.consume(bybit_plan(), max_messages=2)

    assert result.status == ConsumerStatus.MESSAGE_LIMIT_REACHED
    assert result.messages_processed == 2
    assert result.reconnect_attempts == 1
    assert sleeps == [1.0]
    assert factory.calls == [ExchangeName.BYBIT, ExchangeName.BYBIT]
    assert first.closed is True
    assert second.closed is True


def test_consumer_returns_failed_result_after_reconnect_budget_is_exhausted() -> None:
    first = ScriptedTransport(fail_connect=True)
    second = ScriptedTransport(fail_connect=True)
    sleeps: list[float] = []
    consumer = UserStreamConsumer(
        transport_factory=SequenceTransportFactory([first, second]),
        event_handler=lambda event: None,
        sleeper=sleeps.append,
        max_reconnect_attempts=1,
    )

    result = consumer.consume(bybit_plan())

    assert result.status == ConsumerStatus.RECONNECT_EXHAUSTED
    assert result.messages_processed == 0
    assert result.reconnect_attempts == 1
    assert sleeps == [1.0]
    assert first.closed is True
    assert second.closed is True


def test_consumer_does_not_reconnect_or_replay_when_handler_fails() -> None:
    transport = ScriptedTransport(receive_items=[{"topic": "order", "data": []}])
    factory = SequenceTransportFactory([transport])
    sleeps: list[float] = []

    def fail_handler(event: UserStreamEvent) -> None:
        raise ValueError("database write failed")

    consumer = UserStreamConsumer(
        transport_factory=factory,
        event_handler=fail_handler,
        sleeper=sleeps.append,
    )

    with pytest.raises(ValueError, match="database write failed"):
        consumer.consume(bybit_plan())

    assert factory.calls == [ExchangeName.BYBIT]
    assert sleeps == []
    assert transport.closed is True


def test_consumer_honors_stop_request_before_connecting() -> None:
    factory = SequenceTransportFactory([])
    consumer = UserStreamConsumer(
        transport_factory=factory,
        event_handler=lambda event: None,
        should_stop=lambda: True,
    )

    result = consumer.consume(bybit_plan())

    assert result.status == ConsumerStatus.STOPPED
    assert result.messages_processed == 0
    assert result.reconnect_attempts == 0
    assert factory.calls == []


def test_consumer_caps_exponential_reconnect_backoff() -> None:
    transports = [ScriptedTransport(fail_connect=True) for _ in range(4)]
    sleeps: list[float] = []
    consumer = UserStreamConsumer(
        transport_factory=SequenceTransportFactory(transports),
        event_handler=lambda event: None,
        sleeper=sleeps.append,
        max_reconnect_attempts=3,
        initial_backoff_seconds=2,
        max_backoff_seconds=5,
    )

    result = consumer.consume(bybit_plan())

    assert result.status == ConsumerStatus.RECONNECT_EXHAUSTED
    assert result.reconnect_attempts == 3
    assert sleeps == [2, 4, 5]
