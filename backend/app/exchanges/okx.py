from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeHttpClient
from app.exchanges.read_only import ReadOnlyTestnetAdapter
from app.exchanges.testnet_config import get_testnet_endpoint_config


class OKXAdapter(ReadOnlyTestnetAdapter):
    server_time_path = "/api/v5/public/time"
    exchange_info_path = "/api/v5/public/instruments"
    symbol_rules_path = "/api/v5/public/instruments"

    def __init__(
        self,
        *,
        adapters_enabled: bool = False,
        http_client: ExchangeHttpClient | None = None,
    ) -> None:
        super().__init__(
            endpoint_config=get_testnet_endpoint_config(ExchangeName.OKX),
            adapters_enabled=adapters_enabled,
            http_client=http_client,
        )

    def _symbol_rules_params(self, symbol: str) -> dict[str, str]:
        return {"instType": "SPOT", "instId": symbol.replace("USDT", "-USDT")}

    def _normalize_symbol_rules(self, symbol: str, response: dict[str, Any]) -> dict[str, Any]:
        instruments = response.get("data", [])
        normalized_symbol = symbol.replace("USDT", "-USDT")
        symbol_data = next(
            (item for item in instruments if item.get("instId") == normalized_symbol),
            None,
        )
        if symbol_data is None:
            raise ValueError(f"symbol rules not found: {symbol}")
        return {
            "exchange": ExchangeName.OKX.value,
            "symbol": symbol,
            "exchange_symbol": symbol_data.get("instId"),
            "base_asset": symbol_data.get("baseCcy"),
            "quote_asset": symbol_data.get("quoteCcy"),
            "min_quantity": symbol_data.get("minSz"),
            "quantity_step": symbol_data.get("lotSz"),
            "tick_size": symbol_data.get("tickSz"),
            "raw": symbol_data,
        }
