from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from app.db.models.exchange_account import ExchangeName
from app.services.testnet_user_stream import TestnetUserStreamConnectionPlan


class TestnetUserStreamConnectionStatus(StrEnum):
    CREATED = "CREATED"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class TestnetUserStreamEventType(StrEnum):
    ORDER = "ORDER"
    BALANCE = "BALANCE"
    POSITION = "POSITION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TestnetUserStreamEvent:
    exchange_name: ExchangeName
    event_type: TestnetUserStreamEventType
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class TestnetUserStreamSession:
    exchange_account_id: str
    exchange_name: ExchangeName
    websocket_url: str
    status: TestnetUserStreamConnectionStatus


class TestnetUserStreamSocketClient(Protocol):
    def connect(self, websocket_url: str) -> None:
        raise NotImplementedError

    def send_json(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def receive_json(self) -> dict[str, Any]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class TestnetUserStreamRuntime:
    def __init__(self, *, socket_client: TestnetUserStreamSocketClient) -> None:
        self._socket_client = socket_client

    def open_session(self, plan: TestnetUserStreamConnectionPlan) -> TestnetUserStreamSession:
        try:
            self._socket_client.connect(plan.websocket_url)
            status = TestnetUserStreamConnectionStatus.CONNECTED
            if plan.websocket_login_message is not None:
                self._socket_client.send_json(plan.websocket_login_message)
                status = TestnetUserStreamConnectionStatus.AUTHENTICATED
            return TestnetUserStreamSession(
                exchange_account_id=plan.exchange_account_id,
                exchange_name=plan.exchange_name,
                websocket_url=plan.websocket_url,
                status=status,
            )
        except RuntimeError:
            return TestnetUserStreamSession(
                exchange_account_id=plan.exchange_account_id,
                exchange_name=plan.exchange_name,
                websocket_url=plan.websocket_url,
                status=TestnetUserStreamConnectionStatus.FAILED,
            )

    def close_session(self, session: TestnetUserStreamSession) -> TestnetUserStreamSession:
        self._socket_client.close()
        return TestnetUserStreamSession(
            exchange_account_id=session.exchange_account_id,
            exchange_name=session.exchange_name,
            websocket_url=session.websocket_url,
            status=TestnetUserStreamConnectionStatus.CLOSED,
        )


def parse_testnet_user_stream_event(
    *,
    exchange_name: ExchangeName,
    payload: dict[str, Any],
) -> TestnetUserStreamEvent:
    return TestnetUserStreamEvent(
        exchange_name=exchange_name,
        event_type=_event_type(exchange_name=exchange_name, payload=payload),
        raw_payload=dict(payload),
    )


def _event_type(
    *,
    exchange_name: ExchangeName,
    payload: dict[str, Any],
) -> TestnetUserStreamEventType:
    if exchange_name == ExchangeName.BINANCE:
        return _binance_event_type(payload)
    if exchange_name == ExchangeName.BYBIT:
        return _bybit_event_type(payload)
    if exchange_name == ExchangeName.OKX:
        return _okx_event_type(payload)
    return TestnetUserStreamEventType.UNKNOWN


def _binance_event_type(payload: dict[str, Any]) -> TestnetUserStreamEventType:
    event_name = payload.get("e")
    if event_name in {"executionReport", "listStatus"}:
        return TestnetUserStreamEventType.ORDER
    if event_name in {"outboundAccountPosition", "balanceUpdate"}:
        return TestnetUserStreamEventType.BALANCE
    return TestnetUserStreamEventType.UNKNOWN


def _bybit_event_type(payload: dict[str, Any]) -> TestnetUserStreamEventType:
    topic = str(payload.get("topic", ""))
    if topic.startswith("order") or topic.startswith("execution"):
        return TestnetUserStreamEventType.ORDER
    if topic.startswith("wallet"):
        return TestnetUserStreamEventType.BALANCE
    if topic.startswith("position"):
        return TestnetUserStreamEventType.POSITION
    return TestnetUserStreamEventType.UNKNOWN


def _okx_event_type(payload: dict[str, Any]) -> TestnetUserStreamEventType:
    arg = payload.get("arg")
    if not isinstance(arg, dict):
        return TestnetUserStreamEventType.UNKNOWN
    channel = arg.get("channel")
    if channel == "orders":
        return TestnetUserStreamEventType.ORDER
    if channel == "account":
        return TestnetUserStreamEventType.BALANCE
    if channel == "positions":
        return TestnetUserStreamEventType.POSITION
    return TestnetUserStreamEventType.UNKNOWN
