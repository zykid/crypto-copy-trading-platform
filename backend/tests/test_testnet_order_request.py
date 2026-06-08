from decimal import Decimal

import pytest

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import OrderSide, OrderType
from app.exchanges.http_client import ExchangeCredentials, SignedExchangeHttpClient
from app.services.testnet_order_gate import check_testnet_order_gate
from app.services.testnet_order_request import (
    TestnetOrderRequestBlockedError,
    TestnetOrderRequestInput,
    prepare_testnet_order_request,
)


def credentials() -> ExchangeCredentials:
    return ExchangeCredentials(
        api_key="test-api-key",
        api_secret="test-api-secret",
        passphrase="test-passphrase",
    )


def approved_gate(exchange_name: ExchangeName):
    return check_testnet_order_gate(
        exchange_name=exchange_name,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )


def blocked_gate(exchange_name: ExchangeName):
    return check_testnet_order_gate(
        exchange_name=exchange_name,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=False,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )


def test_binance_testnet_order_request_is_signed_post_query() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        timestamp_ms_factory=lambda: 1_700_000_000_000,
    )
    order = TestnetOrderRequestInput(
        exchange_name=ExchangeName.BINANCE,
        symbol="btcusdt",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.0100"),
        client_order_id="client-1",
    )

    prepared = prepare_testnet_order_request(
        order=order,
        gate_result=approved_gate(ExchangeName.BINANCE),
        http_client=client,
        credentials=credentials(),
    )

    assert prepared.method == "POST"
    assert prepared.path == "/api/v3/order"
    assert prepared.body is None
    assert prepared.params["symbol"] == "BTCUSDT"
    assert prepared.params["side"] == "BUY"
    assert prepared.params["type"] == "MARKET"
    assert prepared.params["quantity"] == "0.01"
    assert prepared.params["newClientOrderId"] == "client-1"
    assert prepared.params["signature"]


def test_bybit_testnet_order_request_is_signed_post_json_body() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BYBIT,
        rest_base_url="https://api-testnet.bybit.com",
        timestamp_ms_factory=lambda: 1_700_000_000_001,
    )
    order = TestnetOrderRequestInput(
        exchange_name=ExchangeName.BYBIT,
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.02"),
        price=Decimal("65000.10"),
        client_order_id="client-2",
    )

    prepared = prepare_testnet_order_request(
        order=order,
        gate_result=approved_gate(ExchangeName.BYBIT),
        http_client=client,
        credentials=credentials(),
    )

    assert prepared.method == "POST"
    assert prepared.path == "/v5/order/create"
    assert prepared.params == {}
    assert prepared.body == {
        "category": "spot",
        "symbol": "BTCUSDT",
        "side": "Sell",
        "orderType": "Limit",
        "qty": "0.02",
        "orderLinkId": "client-2",
        "price": "65000.1",
    }
    assert prepared.headers["Content-Type"] == "application/json"
    assert prepared.headers["X-BAPI-SIGN"]


def test_okx_testnet_order_request_uses_demo_signed_post_json_body() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
        iso_timestamp_factory=lambda: "2026-06-08T00:00:00.000Z",
    )
    order = TestnetOrderRequestInput(
        exchange_name=ExchangeName.OKX,
        symbol="btcusdt",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.03"),
        client_order_id="client-3",
    )

    prepared = prepare_testnet_order_request(
        order=order,
        gate_result=approved_gate(ExchangeName.OKX),
        http_client=client,
        credentials=credentials(),
    )

    assert prepared.method == "POST"
    assert prepared.path == "/api/v5/trade/order"
    assert prepared.body == {
        "instId": "BTC-USDT",
        "tdMode": "cash",
        "side": "buy",
        "ordType": "market",
        "sz": "0.03",
        "clOrdId": "client-3",
    }
    assert prepared.headers["x-simulated-trading"] == "1"
    assert prepared.headers["OK-ACCESS-SIGN"]


def test_testnet_order_request_is_blocked_when_gate_is_blocked() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
    )
    order = TestnetOrderRequestInput(
        exchange_name=ExchangeName.BINANCE,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        client_order_id="client-blocked",
    )

    with pytest.raises(TestnetOrderRequestBlockedError):
        prepare_testnet_order_request(
            order=order,
            gate_result=blocked_gate(ExchangeName.BINANCE),
            http_client=client,
            credentials=credentials(),
        )


def test_limit_order_request_requires_price() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
    )
    order = TestnetOrderRequestInput(
        exchange_name=ExchangeName.OKX,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        client_order_id="client-no-price",
    )

    with pytest.raises(ValueError, match="limit orders require price"):
        prepare_testnet_order_request(
            order=order,
            gate_result=approved_gate(ExchangeName.OKX),
            http_client=client,
            credentials=credentials(),
        )
