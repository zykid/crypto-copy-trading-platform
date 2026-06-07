from decimal import Decimal
from typing import Any

from app.db.models.trading import OrderSide, OrderType
from app.exchanges.base import ExchangeAdapter
from app.exchanges.testnet_config import ExchangeEndpointConfig


class TestnetAdapterDisabledError(RuntimeError):
    pass


class TestnetAdapterNotImplementedError(NotImplementedError):
    pass


class TestnetTradingNotSupportedError(RuntimeError):
    pass


class ReadOnlyTestnetAdapter(ExchangeAdapter):
    def __init__(self, *, endpoint_config: ExchangeEndpointConfig, adapters_enabled: bool) -> None:
        self.endpoint_config = endpoint_config
        self.adapters_enabled = adapters_enabled

    def get_balances(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        return self._read_only_request("get_balances")

    def get_positions(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        return self._read_only_request("get_positions")

    def get_open_orders(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        return self._read_only_request("get_open_orders")

    def get_symbol_rules(self, *, symbol: str) -> dict[str, Any]:
        self._ensure_enabled()
        return self._read_only_request("get_symbol_rules", symbol=symbol.upper())

    def get_order_status(self, *, exchange_order_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        return self._read_only_request("get_order_status", exchange_order_id=exchange_order_id)

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
            "testnet order placement is not implemented in phase 3 step 2"
        )

    def cancel_order(self, *, exchange_order_id: str) -> dict[str, Any]:
        raise TestnetTradingNotSupportedError(
            "testnet order cancellation is not implemented in phase 3 step 2"
        )

    def _ensure_enabled(self) -> None:
        if not self.adapters_enabled:
            raise TestnetAdapterDisabledError("testnet adapters are disabled by configuration")

    def _read_only_request(self, operation: str, **params: object) -> Any:
        raise TestnetAdapterNotImplementedError(
            f"{operation} is not implemented until an exchange HTTP client is added"
        )
