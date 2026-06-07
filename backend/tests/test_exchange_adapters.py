from decimal import Decimal
from typing import Any

import pytest

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import OrderSide, OrderType
from app.exchanges.binance import BinanceAdapter
from app.exchanges.bybit import BybitAdapter
from app.exchanges.factory import create_exchange_adapter
from app.exchanges.http_client import ExchangeCredentials, ExchangeSecurityType
from app.exchanges.mock import MockExchange
from app.exchanges.okx import OKXAdapter
from app.exchanges.read_only import (
    TestnetAdapterCredentialsError,
    TestnetAdapterDisabledError,
    TestnetAdapterNotImplementedError,
    TestnetTradingNotSupportedError,
)

PublicResponseKey = tuple[str, tuple[tuple[str, str], ...]]
PrivateResponseKey = tuple[str, tuple[tuple[str, str], ...], ExchangeSecurityType]
PrivateCall = tuple[str, dict[str, str] | None, ExchangeSecurityType, str]


class FakeHttpClient:
    def __init__(
        self,
        responses: dict[PublicResponseKey, dict[str, Any]],
        private_responses: dict[PrivateResponseKey, dict[str, Any]] | None = None,
    ):
        self.responses = responses
        self.private_responses = private_responses or {}
        self.calls: list[tuple[str, dict[str, str] | None]] = []
        self.private_calls: list[PrivateCall] = []

    def get_public(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        key = (path, tuple(sorted((params or {}).items())))
        return self.responses[key]

    def get_private(
        self,
        path: str,
        *,
        credentials: ExchangeCredentials,
        params: dict[str, str] | None = None,
        security_type: ExchangeSecurityType = ExchangeSecurityType.SIGNED,
    ) -> dict[str, Any]:
        self.private_calls.append((path, params, security_type, credentials.api_key))
        key = (path, tuple(sorted((params or {}).items())), security_type)
        return self.private_responses[key]


def credentials() -> ExchangeCredentials:
    return ExchangeCredentials(
        api_key="test-api-key",
        api_secret="test-api-secret",
        passphrase="test-passphrase",
    )


def test_factory_returns_mock_adapter() -> None:
    adapter = create_exchange_adapter(ExchangeName.MOCK)

    assert isinstance(adapter, MockExchange)


def test_factory_returns_testnet_adapter_skeletons() -> None:
    assert isinstance(create_exchange_adapter(ExchangeName.BINANCE), BinanceAdapter)
    assert isinstance(create_exchange_adapter(ExchangeName.BYBIT), BybitAdapter)
    assert isinstance(create_exchange_adapter(ExchangeName.OKX), OKXAdapter)


def test_factory_passes_credentials_to_testnet_adapters() -> None:
    adapter = create_exchange_adapter(
        ExchangeName.BINANCE,
        testnet_adapters_enabled=True,
        http_client=FakeHttpClient({}),
        credentials=credentials(),
    )

    assert isinstance(adapter, BinanceAdapter)
    assert adapter.credentials.api_key == "test-api-key"


def test_testnet_read_only_methods_are_disabled_by_default() -> None:
    adapter = BinanceAdapter()

    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_symbol_rules(symbol="btcusdt")
    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_balances()
    with pytest.raises(TestnetAdapterDisabledError):
        adapter.get_positions()


def test_enabled_testnet_adapter_requires_http_client_for_public_methods() -> None:
    adapter = BybitAdapter(adapters_enabled=True)

    with pytest.raises(RuntimeError, match="exchange HTTP client is not configured"):
        adapter.get_symbol_rules(symbol="BTCUSDT")


def test_authenticated_read_only_methods_require_credentials() -> None:
    adapter = BybitAdapter(adapters_enabled=True, http_client=FakeHttpClient({}))

    with pytest.raises(TestnetAdapterCredentialsError):
        adapter.get_balances()
    with pytest.raises(TestnetAdapterCredentialsError):
        adapter.get_positions()
    with pytest.raises(TestnetAdapterNotImplementedError):
        adapter.get_open_orders()


def test_binance_authenticated_read_only_methods_use_fake_client() -> None:
    client = FakeHttpClient(
        {},
        {
            (
                "/api/v3/account",
                (),
                ExchangeSecurityType.SIGNED,
            ): {
                "balances": [
                    {"asset": "USDT", "free": "100", "locked": "2"},
                    {"asset": "BTC", "free": "0.1", "locked": "0"},
                ]
            }
        },
    )
    adapter = BinanceAdapter(
        adapters_enabled=True,
        http_client=client,
        credentials=credentials(),
    )

    balances = adapter.get_balances()
    positions = adapter.get_positions()

    assert balances[0] == {
        "asset": "USDT",
        "free": "100",
        "locked": "2",
        "total": None,
        "raw": {"asset": "USDT", "free": "100", "locked": "2"},
    }
    assert balances[1]["asset"] == "BTC"
    assert positions == []
    assert client.private_calls == [
        ("/api/v3/account", None, ExchangeSecurityType.SIGNED, "test-api-key"),
        ("/api/v3/account", None, ExchangeSecurityType.SIGNED, "test-api-key"),
    ]


def test_bybit_authenticated_read_only_methods_use_fake_client() -> None:
    client = FakeHttpClient(
        {},
        {
            (
                "/v5/account/wallet-balance",
                (("accountType", "UNIFIED"),),
                ExchangeSecurityType.SIGNED,
            ): {
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "USDT", "walletBalance": "100", "locked": "1"}
                            ]
                        }
                    ]
                }
            },
            (
                "/v5/position/list",
                (("category", "linear"), ("settleCoin", "USDT")),
                ExchangeSecurityType.SIGNED,
            ): {
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "Buy",
                            "size": "0.1",
                            "avgPrice": "100",
                            "unrealisedPnl": "1",
                        }
                    ]
                }
            },
        },
    )
    adapter = BybitAdapter(
        adapters_enabled=True,
        http_client=client,
        credentials=credentials(),
    )

    balances = adapter.get_balances()
    positions = adapter.get_positions()

    assert balances[0]["asset"] == "USDT"
    assert balances[0]["total"] == "100"
    assert balances[0]["locked"] == "1"
    assert positions[0]["symbol"] == "BTCUSDT"
    assert positions[0]["side"] == "Buy"
    assert positions[0]["quantity"] == "0.1"


def test_okx_authenticated_read_only_methods_use_demo_security_type() -> None:
    client = FakeHttpClient(
        {},
        {
            (
                "/api/v5/account/balance",
                (),
                ExchangeSecurityType.OKX_DEMO_SIGNED,
            ): {
                "data": [
                    {
                        "details": [
                            {
                                "ccy": "USDT",
                                "availBal": "100",
                                "frozenBal": "1",
                                "cashBal": "101",
                            }
                        ]
                    }
                ]
            },
            (
                "/api/v5/account/positions",
                (),
                ExchangeSecurityType.OKX_DEMO_SIGNED,
            ): {
                "data": [
                    {
                        "instId": "BTC-USDT",
                        "posSide": "long",
                        "pos": "0.1",
                        "avgPx": "100",
                        "upl": "1",
                    }
                ]
            },
        },
    )
    adapter = OKXAdapter(
        adapters_enabled=True,
        http_client=client,
        credentials=credentials(),
    )

    balances = adapter.get_balances()
    positions = adapter.get_positions()

    assert balances[0]["asset"] == "USDT"
    assert balances[0]["free"] == "100"
    assert balances[0]["locked"] == "1"
    assert positions[0]["symbol"] == "BTC-USDT"
    assert positions[0]["side"] == "long"
    assert client.private_calls[0][2] == ExchangeSecurityType.OKX_DEMO_SIGNED
    assert client.private_calls[1][2] == ExchangeSecurityType.OKX_DEMO_SIGNED


def test_binance_public_methods_use_fake_client() -> None:
    client = FakeHttpClient(
        {
            ("/api/v3/time", ()): {"serverTime": 123456789},
            ("/api/v3/exchangeInfo", ()): {"timezone": "UTC", "symbols": []},
            (
                "/api/v3/exchangeInfo",
                (("symbol", "BTCUSDT"),),
            ): {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "baseAsset": "BTC",
                        "quoteAsset": "USDT",
                        "filters": [
                            {
                                "filterType": "LOT_SIZE",
                                "minQty": "0.00001000",
                                "maxQty": "9000.00000000",
                                "stepSize": "0.00001000",
                            },
                            {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"},
                        ],
                    }
                ]
            },
        }
    )
    adapter = BinanceAdapter(adapters_enabled=True, http_client=client)

    assert adapter.get_server_time() == {"serverTime": 123456789}
    assert adapter.get_exchange_info() == {"timezone": "UTC", "symbols": []}
    rules = adapter.get_symbol_rules(symbol="btcusdt")

    assert rules["exchange"] == "binance"
    assert rules["symbol"] == "BTCUSDT"
    assert rules["base_asset"] == "BTC"
    assert rules["quote_asset"] == "USDT"
    assert rules["min_quantity"] == "0.00001000"
    assert rules["quantity_step"] == "0.00001000"
    assert rules["min_notional"] == "5.00000000"


def test_bybit_symbol_rules_use_fake_client() -> None:
    client = FakeHttpClient(
        {
            (
                "/v5/market/instruments-info",
                (("category", "spot"), ("symbol", "BTCUSDT")),
            ): {
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "baseCoin": "BTC",
                            "quoteCoin": "USDT",
                            "lotSizeFilter": {
                                "minOrderQty": "0.00001",
                                "maxOrderQty": "71",
                                "basePrecision": "0.000001",
                                "minOrderAmt": "1",
                            },
                            "priceFilter": {"tickSize": "0.01"},
                        }
                    ]
                }
            },
        }
    )
    adapter = BybitAdapter(adapters_enabled=True, http_client=client)

    rules = adapter.get_symbol_rules(symbol="BTCUSDT")

    assert rules["exchange"] == "bybit"
    assert rules["base_asset"] == "BTC"
    assert rules["quote_asset"] == "USDT"
    assert rules["min_quantity"] == "0.00001"
    assert rules["min_notional"] == "1"
    assert rules["tick_size"] == "0.01"


def test_okx_symbol_rules_use_fake_client() -> None:
    client = FakeHttpClient(
        {
            (
                "/api/v5/public/instruments",
                (("instId", "BTC-USDT"), ("instType", "SPOT")),
            ): {
                "data": [
                    {
                        "instId": "BTC-USDT",
                        "baseCcy": "BTC",
                        "quoteCcy": "USDT",
                        "minSz": "0.00001",
                        "lotSz": "0.00000001",
                        "tickSz": "0.1",
                    }
                ]
            },
        }
    )
    adapter = OKXAdapter(adapters_enabled=True, http_client=client)

    rules = adapter.get_symbol_rules(symbol="BTCUSDT")

    assert rules["exchange"] == "okx"
    assert rules["exchange_symbol"] == "BTC-USDT"
    assert rules["base_asset"] == "BTC"
    assert rules["quote_asset"] == "USDT"
    assert rules["min_quantity"] == "0.00001"
    assert rules["quantity_step"] == "0.00000001"
    assert rules["tick_size"] == "0.1"


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
