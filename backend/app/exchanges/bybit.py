from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials, ExchangeHttpClient
from app.exchanges.read_only import ReadOnlyTestnetAdapter
from app.exchanges.testnet_config import get_testnet_endpoint_config


class BybitAdapter(ReadOnlyTestnetAdapter):
    server_time_path = "/v5/market/time"
    exchange_info_path = "/v5/market/instruments-info"
    symbol_rules_path = "/v5/market/instruments-info"
    balances_path = "/v5/account/wallet-balance"
    positions_path = "/v5/position/list"

    def __init__(
        self,
        *,
        adapters_enabled: bool = False,
        http_client: ExchangeHttpClient | None = None,
        credentials: ExchangeCredentials | None = None,
    ) -> None:
        super().__init__(
            endpoint_config=get_testnet_endpoint_config(ExchangeName.BYBIT),
            adapters_enabled=adapters_enabled,
            http_client=http_client,
            credentials=credentials,
        )

    def _balances_params(self) -> dict[str, str]:
        return {"accountType": "UNIFIED"}

    def _positions_params(self) -> dict[str, str]:
        return {"category": "linear", "settleCoin": "USDT"}

    def _symbol_rules_params(self, symbol: str) -> dict[str, str]:
        return {"category": "spot", "symbol": symbol}

    def _normalize_symbol_rules(self, symbol: str, response: dict[str, Any]) -> dict[str, Any]:
        instruments = response.get("result", {}).get("list", [])
        symbol_data = next((item for item in instruments if item.get("symbol") == symbol), None)
        if symbol_data is None:
            raise ValueError(f"symbol rules not found: {symbol}")
        lot_filter = symbol_data.get("lotSizeFilter", {})
        price_filter = symbol_data.get("priceFilter", {})
        return {
            "exchange": ExchangeName.BYBIT.value,
            "symbol": symbol,
            "base_asset": symbol_data.get("baseCoin"),
            "quote_asset": symbol_data.get("quoteCoin"),
            "min_quantity": lot_filter.get("minOrderQty"),
            "max_quantity": lot_filter.get("maxOrderQty"),
            "quantity_step": lot_filter.get("basePrecision"),
            "min_notional": lot_filter.get("minOrderAmt"),
            "tick_size": price_filter.get("tickSize"),
            "raw": symbol_data,
        }

    def _normalize_balances(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        balances: list[dict[str, Any]] = []
        for account in response.get("result", {}).get("list", []):
            for coin in account.get("coin", []):
                balances.append(
                    {
                        "exchange": ExchangeName.BYBIT.value,
                        "asset": coin.get("coin"),
                        "free": coin.get("walletBalance"),
                        "locked": coin.get("locked"),
                        "total": coin.get("walletBalance"),
                        "raw": coin,
                    }
                )
        return balances

    def _normalize_positions(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "exchange": ExchangeName.BYBIT.value,
                "symbol": item.get("symbol"),
                "side": item.get("side"),
                "quantity": item.get("size"),
                "entry_price": item.get("avgPrice"),
                "unrealized_pnl": item.get("unrealisedPnl"),
                "raw": item,
            }
            for item in response.get("result", {}).get("list", [])
        ]
