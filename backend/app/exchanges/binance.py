from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeHttpClient
from app.exchanges.read_only import ReadOnlyTestnetAdapter
from app.exchanges.testnet_config import get_testnet_endpoint_config


class BinanceAdapter(ReadOnlyTestnetAdapter):
    server_time_path = "/api/v3/time"
    exchange_info_path = "/api/v3/exchangeInfo"
    symbol_rules_path = "/api/v3/exchangeInfo"

    def __init__(
        self,
        *,
        adapters_enabled: bool = False,
        http_client: ExchangeHttpClient | None = None,
    ) -> None:
        super().__init__(
            endpoint_config=get_testnet_endpoint_config(ExchangeName.BINANCE),
            adapters_enabled=adapters_enabled,
            http_client=http_client,
        )

    def _normalize_symbol_rules(self, symbol: str, response: dict[str, Any]) -> dict[str, Any]:
        symbols = response.get("symbols", [])
        symbol_data = next((item for item in symbols if item.get("symbol") == symbol), None)
        if symbol_data is None:
            raise ValueError(f"symbol rules not found: {symbol}")
        filters = {item.get("filterType"): item for item in symbol_data.get("filters", [])}
        lot_size = filters.get("LOT_SIZE", {})
        min_notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
        return {
            "exchange": ExchangeName.BINANCE.value,
            "symbol": symbol,
            "base_asset": symbol_data.get("baseAsset"),
            "quote_asset": symbol_data.get("quoteAsset"),
            "min_quantity": lot_size.get("minQty"),
            "max_quantity": lot_size.get("maxQty"),
            "quantity_step": lot_size.get("stepSize"),
            "min_notional": min_notional.get("minNotional"),
            "raw": symbol_data,
        }
