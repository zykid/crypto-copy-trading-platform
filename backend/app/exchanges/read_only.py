from decimal import Decimal
from typing import Any

from app.db.models.trading import OrderSide, OrderType
from app.exchanges.base import ExchangeAdapter
from app.exchanges.http_client import ExchangeHttpClient, NoopExchangeHttpClient
from app.exchanges.testnet_config import ExchangeEndpointConfig


class TestnetAdapterDisabledError(RuntimeError):
    pass


class TestnetAdapterNotImplementedError(NotImplementedError):
    pass


class TestnetTradingNotSupportedError(RuntimeError):
    pass


class ReadOnlyTestnetAdapter(ExchangeAdapter):
    server_time_path: str
    exchange_info_path: str
    symbol_rules_path: str

    def __init__(
        self,
        *,
        endpoint_config: ExchangeEndpointConfig,
        adapters_enabled: bool,
        http_client: ExchangeHttpClient | None = None,
    ) -> None:
        self.endpoint_config = endpoint_config
        self.adapters_enabled = adapters_enabled
        self.http_client = http_client or NoopExchangeHttpClient()

    def get_server_time(self) -> dict[str, Any]:
        self._ensure_enabled()
        return self.http_client.get_public(self.server_time_path)

    def get_exchange_info(self) -> dict[str, Any]:
        self._ensure_enabled()
        return self.http_client.get_public(self.exchange_info_path)

    def get_balances(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        raise TestnetAdapterNotImplementedError(
            "authenticated balances are not implemented in phase 3 step 3"
        )

    def get_positions(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        raise TestnetAdapterNotImplementedError(
            "authenticated positions are not implemented in phase 3 step 3"
        )

    def get_open_orders(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        raise TestnetAdapterNotImplementedError(
            "authenticated open orders are not implemented in phase 3 step 3"
        )

    def get_symbol_rules(self, *, symbol: str) -> dict[str, Any]:
        self._ensure_enabled()
        response = self.http_client.get_public(
            self.symbol_rules_path,
            params=self._symbol_rules_params(symbol.upper()),
        )
        return self._normalize_symbol_rules(symbol.upper(), response)

    def get_order_status(self, *, exchange_order_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        raise TestnetAdapterNotImplementedError(
            "authenticated order status is not implemented in phase 3 step 3"
        )

    def place_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None,
    ) -> dict[str, Any]:
        raise TestnetTradingNotSupportedError(
            "testnet order placement is not implemented in phase 3 step 3"
        )

    def cancel_order(self, *, exchange_order_id: str) -> dict[str, Any]:
        raise TestnetTradingNotSupportedError(
            "testnet order cancellation is not implemented in phase 3 step 3"
        )

    def _ensure_enabled(self) -> None:
        if not self.adapters_enabled:
            raise TestnetAdapterDisabledError("testnet adapters are disabled by configuration")

    def _symbol_rules_params(self, symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    def _normalize_symbol_rules(self, symbol: str, response: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
