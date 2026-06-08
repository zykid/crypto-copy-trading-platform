from decimal import Decimal
from typing import Any

import pytest

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import OrderSide, OrderType
from app.exchanges.http_client import (
    ExchangeCredentials,
    PreparedExchangeRequest,
    SignedExchangeHttpClient,
)
from app.services.rate_limit_service import RateLimitExceededError, RuntimeRateLimitService
from app.services.testnet_order_execution import execute_testnet_order
from app.services.testnet_order_gate import check_testnet_order_gate
from app.services.testnet_order_request import (
    TestnetOrderRequestBlockedError,
    TestnetOrderRequestInput,
)


class RecordingTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[PreparedExchangeRequest] = []

    def request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        self.requests.append(prepared)
        return self.response


class ControlledClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def credentials() -> ExchangeCredentials:
    return ExchangeCredentials(
        api_key="test-api-key",
        api_secret="test-api-secret",
        passphrase="test-passphrase",
    )


def gate_result(*, approved: bool):
    return check_testnet_order_gate(
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=approved,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )


def market_order() -> TestnetOrderRequestInput:
    return TestnetOrderRequestInput(
        exchange_name=ExchangeName.BINANCE,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        client_order_id="client-exec-1",
    )


def test_execute_testnet_order_sends_prepared_request_through_injected_transport() -> None:
    transport = RecordingTransport(
        response={"orderId": "exchange-order-1", "clientOrderId": "client-exec-1"}
    )
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        transport=transport,
        timestamp_ms_factory=lambda: 1_700_000_000_010,
    )

    result = execute_testnet_order(
        order=market_order(),
        gate_result=gate_result(approved=True),
        http_client=client,
        credentials=credentials(),
    )

    assert result.exchange_name == ExchangeName.BINANCE
    assert result.client_order_id == "client-exec-1"
    assert result.request_method == "POST"
    assert result.request_path == "/api/v3/order"
    assert result.exchange_response == {
        "orderId": "exchange-order-1",
        "clientOrderId": "client-exec-1",
    }
    assert len(transport.requests) == 1
    assert transport.requests[0].params["newClientOrderId"] == "client-exec-1"
    assert transport.requests[0].params["signature"]


def test_execute_testnet_order_result_does_not_expose_request_credentials() -> None:
    transport = RecordingTransport(response={"status": "ACCEPTED"})
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        transport=transport,
    )

    result = execute_testnet_order(
        order=market_order(),
        gate_result=gate_result(approved=True),
        http_client=client,
        credentials=credentials(),
    )

    assert not hasattr(result, "headers")
    assert not hasattr(result, "params")
    assert not hasattr(result, "body")


def test_execute_testnet_order_does_not_send_when_gate_is_blocked() -> None:
    transport = RecordingTransport(response={"should_not": "send"})
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        transport=transport,
    )

    with pytest.raises(TestnetOrderRequestBlockedError):
        execute_testnet_order(
            order=market_order(),
            gate_result=gate_result(approved=False),
            http_client=client,
            credentials=credentials(),
        )

    assert transport.requests == []


def test_execute_testnet_order_does_not_send_when_rate_limited() -> None:
    transport = RecordingTransport(response={"status": "ACCEPTED"})
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        transport=transport,
    )
    limiter = RuntimeRateLimitService(clock=ControlledClock())

    execute_testnet_order(
        order=market_order(),
        gate_result=gate_result(approved=True),
        http_client=client,
        credentials=credentials(),
        rate_limiter=limiter,
        exchange_account_id="acct-1",
    )

    with pytest.raises(RateLimitExceededError):
        execute_testnet_order(
            order=market_order(),
            gate_result=gate_result(approved=True),
            http_client=client,
            credentials=credentials(),
            rate_limiter=limiter,
            exchange_account_id="acct-1",
        )

    assert len(transport.requests) == 1
