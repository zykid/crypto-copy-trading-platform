from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials, ExchangeHttpClient, ExchangeSecurityType
from app.exchanges.read_only import ReadOnlyTestnetAdapter
from app.exchanges.testnet_config import get_testnet_endpoint_config


class OKXAdapter(ReadOnlyTestnetAdapter):
    server_time_path = "/api/v5/public/time"
    exchange_info_path = "/api/v5/public/instruments"
    symbol_rules_path = "/api/v5/public/instruments"
    balances_path = "/api/v5/account/balance"
    positions_path = "/api/v5/account/positions"
    private_security_type = ExchangeSecurityType.OKX_DEMO_SIGNED

    def __init__(
        self,
        *,
        adapters_enabled: bool = False,
        http_client: ExchangeHttpClient | None = None,
        credentials: ExchangeCredentials | None = None,
    ) -> None:
        super().__init__(
            endpoint_config=get_testnet_endpoint_config(ExchangeName.OKX),
            adapters_enabled=adapters_enabled,
            http_client=http_client,
            credentials=credentials,
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

    def _normalize_balances(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        balances: list[dict[str, Any]] = []
        for account in response.get("data", []):
            for detail in account.get("details", []):
                balances.append(
                    {
                        "exchange": ExchangeName.OKX.value,
                        "asset": detail.get("ccy"),
                        "free": detail.get("availBal"),
                        "locked": detail.get("frozenBal"),
                        "total": detail.get("cashBal"),
                        "raw": detail,
                    }
                )
        return balances

    def _normalize_positions(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "exchange": ExchangeName.OKX.value,
                "symbol": item.get("instId"),
                "side": item.get("posSide"),
                "quantity": item.get("pos"),
                "entry_price": item.get("avgPx"),
                "unrealized_pnl": item.get("upl"),
                "raw": item,
            }
            for item in response.get("data", [])
        ]
