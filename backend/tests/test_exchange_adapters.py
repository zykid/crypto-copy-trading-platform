from decimal import Decimal

import pytest

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import OrderSide, OrderType
from app.exchanges.binance import BinanceAdapter
from app.exchanges.bybit import BybitAdapter
from app.exchanges.factory import create_exchange_adapter
from app.exchanges.mock import MockExchange
from app.exchanges.okx import OKXAdapter
from app.exchanges.read_only import (
    TestnetAdapterDisabledError,
    TestnetAdapterNotImplementedError,
    TestnetTradingNotSupportedError,
)


def test_factory_returns_mock_adapter() -> None:
    adapter = create_exchange_adapter(ExchangeName.MOCK)

    assert isinstance(adapter, MockExchange)


def test_factory_returns_testnet_adapter_skeletons() -> None:
    assert isinstance(create_exchange_adapter(ExchangeName.BINANCE), BinanceAdapter)
    assert isinstance(create_exchange_adapter(ExchangeName.BYBIT), BybitAdapter)
    assert isinstance(create_exchange_adapter(ExchangeName.OKX), OKXAdapter)


def test_testnet_read_only_methods_are_disabled_by_default() -> None:
    adapter = BinanceAdapter()

    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_symbol_rules(symbol="btcusdt")
    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_balances()
    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_positions()


def test_enabled_testnet_adapter_still_has_no_http_client() -> None:
    adapter = BybitAdapter(adapters_enabled=True)

    with pytest.raises(TestnetAdapterNotImplementedError):
        adapter.get_symbol_rules(symbol="BTCUSDT")
    with pytest.raises(TestnetAdapterNotImplementedError):
        adapter.get_open_orders()


def test_testnet_trading_methods_are_not_supported() -> None:
    adapter = OKXAdapter(adapters_enabled=True)

    with pytest.raises(TestnetTradingNotSupportedError):
        adapter.place_order(
            client_order_id="test-client-order-id",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
            price=None,
        )
    with pytest.raises(TestnetTradingNotSupportedError):
        adapter.cancel_order(exchange_order_id="test-order-id")


def test_adapter_endpoint_metadata_is_available_without_network() -> None:
    adapter = OKXAdapter()

    assert adapter.endpoint_config.rest_base_url == "https://openapi.okx.com"
    assert adapter.endpoint_config.demo_header_required is True
