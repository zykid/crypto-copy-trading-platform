from decimal import Decimal
from typing import Any

from app.db.models.trading import OrderSide, OrderType
from app.exchanges.base import ExchangeAdapter
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeHttpClient,
    ExchangeSecurityType,
    NoopExchangeHttpClient,
)
from app.exchanges.rate_limit import ExchangeRateLimitConfig, get_exchange_rate_limit_config
from app.exchanges.testnet_config import ExchangeEndpointConfig


class TestnetAdapterDisabledError(RuntimeError):
    pass


class TestnetAdapterCredentialsError(RuntimeError):
    pass


class TestnetAdapterNotImplementedError(NotImplementedError):
    pass


class TestnetTradingNotSupportedError(RuntimeError):
    pass


class ReadOnlyTestnetAdapter(ExchangeAdapter):
    server_time_path: str
    exchange_info_path: str
    symbol_rules_path: str
    balances_path: str
    positions_path: str
    private_security_type = ExchangeSecurityType.SIGNED

    def __init__(
        self,
        *,
        endpoint_config: ExchangeEndpointConfig,
        adapters_enabled: bool,
        http_client: ExchangeHttpClient | None = None,
        credentials: ExchangeCredentials | None = None,
    ) -> None:
        self.endpoint_config = endpoint_config
        self.rate_limit_config: ExchangeRateLimitConfig = get_exchange_rate_limit_config(
            endpoint_config.exchange_name
        )
        self.adapters_enabled = adapters_enabled
        self.http_client = http_client or NoopExchangeHttpClient()
        self.credentials = credentials

    def get_server_time(self) -> dict[str, Any]:
        self._ensure_enabled()
        return self.http_client.get_public(self.server_time_path)

    def get_exchange_info(self) -> dict[str, Any]:
        self._ensure_enabled()
        return self.http_client.get_public(self.exchange_info_path)

    def get_balances(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        response = self.http_client.get_private(
            self.balances_path,
            credentials=self._require_credentials(),
            params=self._balances_params(),
            security_type=self.private_security_type,
        )
        return self._normalize_balances(response)

    def get_positions(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        response = self.http_client.get_private(
            self.positions_path,
            credentials=self._require_credentials(),
            params=self._positions_params(),
            security_type=self.private_security_type,
        )
        return self._normalize_positions(response)

    def get_open_orders(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        raise TestnetAdapterNotImplementedError(
            "authenticated open orders are not implemented in phase 3 step 4"
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
            "authenticated order status is not implemented in phase 3 step 4"
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
            "testnet order placement is not implemented in phase 3 step 4"
        )

    def cancel_order(self, *, exchange_order_id: str) -> dict[str, Any]:
        raise TestnetTradingNotSupportedError(
            "testnet order cancellation is not implemented in phase 3 step 4"
        )

    def _ensure_enabled(self) -> None:
        if not self.adapters_enabled:
            raise TestnetAdapterDisabledError("testnet adapters are disabled by configuration")

    def _require_credentials(self) -> ExchangeCredentials:
        if self.credentials is None:
            raise TestnetAdapterCredentialsError("exchange credentials are not configured")
        return self.credentials

    def _balances_params(self) -> dict[str, str] | None:
        return None

    def _positions_params(self) -> dict[str, str] | None:
        return None

    def _symbol_rules_params(self, symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    def _normalize_symbol_rules(self, symbol: str, response: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _normalize_balances(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _normalize_positions(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError
