from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from time import sleep
from typing import Protocol

from app.db.models.exchange_account import ExchangeName
from app.services.testnet_user_stream import TestnetUserStreamConnectionPlan
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamConnectionStatus,
    TestnetUserStreamEvent,
    TestnetUserStreamRuntime,
    TestnetUserStreamSocketClient,
    parse_testnet_user_stream_event,
)
from app.services.testnet_websocket_transport import TestnetWebSocketTransportError


class TestnetUserStreamConsumerStatus(StrEnum):
    STOPPED = "STOPPED"
    MESSAGE_LIMIT_REACHED = "MESSAGE_LIMIT_REACHED"
    RECONNECT_EXHAUSTED = "RECONNECT_EXHAUSTED"


@dataclass(frozen=True)
class TestnetUserStreamConsumerResult:
    status: TestnetUserStreamConsumerStatus
    messages_processed: int
    reconnect_attempts: int


class TestnetUserStreamTransportFactory(Protocol):
    def __call__(
        self,
        exchange_name: ExchangeName,
    ) -> TestnetUserStreamSocketClient: ...


class TestnetUserStreamConsumer:
    def __init__(
        self,
        *,
        transport_factory: TestnetUserStreamTransportFactory,
        event_handler: Callable[[TestnetUserStreamEvent], None],
        should_stop: Callable[[], bool] = lambda: False,
        sleeper: Callable[[float], None] = sleep,
        max_reconnect_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        if max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts must not be negative")
        if initial_backoff_seconds <= 0 or max_backoff_seconds <= 0:
            raise ValueError("reconnect backoff must be positive")
        self._transport_factory = transport_factory
        self._event_handler = event_handler
        self._should_stop = should_stop
        self._sleeper = sleeper
        self._max_reconnect_attempts = max_reconnect_attempts
        self._initial_backoff_seconds = initial_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds

    def consume(
        self,
        plan: TestnetUserStreamConnectionPlan,
        *,
        max_messages: int | None = None,
    ) -> TestnetUserStreamConsumerResult:
        if max_messages is not None and max_messages <= 0:
            raise ValueError("max_messages must be positive")

        messages_processed = 0
        reconnect_attempts = 0
        while True:
            if self._should_stop():
                return _result(
                    status=TestnetUserStreamConsumerStatus.STOPPED,
                    messages_processed=messages_processed,
                    reconnect_attempts=reconnect_attempts,
                )

            transport = self._transport_factory(plan.exchange_name)
            runtime = TestnetUserStreamRuntime(socket_client=transport)
            session = runtime.open_session(plan)
            if session.status == TestnetUserStreamConnectionStatus.FAILED:
                _close_transport(transport)
                if reconnect_attempts >= self._max_reconnect_attempts:
                    return _result(
                        status=TestnetUserStreamConsumerStatus.RECONNECT_EXHAUSTED,
                        messages_processed=messages_processed,
                        reconnect_attempts=reconnect_attempts,
                    )
                reconnect_attempts += 1
                self._sleep_before_reconnect(reconnect_attempts)
                continue

            connection_failed = False
            try:
                while not self._should_stop():
                    try:
                        payload = transport.receive_json()
                    except TestnetWebSocketTransportError:
                        connection_failed = True
                        break

                    event = parse_testnet_user_stream_event(
                        exchange_name=plan.exchange_name,
                        payload=payload,
                    )
                    self._event_handler(event)
                    messages_processed += 1
                    if (
                        max_messages is not None
                        and messages_processed >= max_messages
                    ):
                        return _result(
                            status=TestnetUserStreamConsumerStatus.MESSAGE_LIMIT_REACHED,
                            messages_processed=messages_processed,
                            reconnect_attempts=reconnect_attempts,
                        )
            finally:
                _close_transport(transport)

            if self._should_stop():
                return _result(
                    status=TestnetUserStreamConsumerStatus.STOPPED,
                    messages_processed=messages_processed,
                    reconnect_attempts=reconnect_attempts,
                )
            if not connection_failed:
                return _result(
                    status=TestnetUserStreamConsumerStatus.STOPPED,
                    messages_processed=messages_processed,
                    reconnect_attempts=reconnect_attempts,
                )
            if reconnect_attempts >= self._max_reconnect_attempts:
                return _result(
                    status=TestnetUserStreamConsumerStatus.RECONNECT_EXHAUSTED,
                    messages_processed=messages_processed,
                    reconnect_attempts=reconnect_attempts,
                )
            reconnect_attempts += 1
            self._sleep_before_reconnect(reconnect_attempts)

    def _sleep_before_reconnect(self, reconnect_attempt: int) -> None:
        delay = min(
            self._initial_backoff_seconds * (2 ** (reconnect_attempt - 1)),
            self._max_backoff_seconds,
        )
        self._sleeper(delay)


def _close_transport(transport: TestnetUserStreamSocketClient) -> None:
    try:
        transport.close()
    except RuntimeError:
        pass


def _result(
    *,
    status: TestnetUserStreamConsumerStatus,
    messages_processed: int,
    reconnect_attempts: int,
) -> TestnetUserStreamConsumerResult:
    return TestnetUserStreamConsumerResult(
        status=status,
        messages_processed=messages_processed,
        reconnect_attempts=reconnect_attempts,
    )
