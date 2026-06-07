from decimal import Decimal
from typing import Any

from app.db.models.trading import OrderExecutionStatus, OrderSide, OrderType
from app.exchanges.base import ExchangeAdapter


class MockExchange(ExchangeAdapter):
    def __init__(self) -> None:
        self.orders: dict[str, dict[str, Any]] = {}

    def get_server_time(self) -> dict[str, Any]:
        return {"server_time": 0, "source": "mock"}

    def get_exchange_info(self) -> dict[str, Any]:
        return {"exchange": "mock", "symbols": ["BTCUSDT"]}

    def get_balances(self) -> list[dict[str, Any]]:
        return [{"asset": "USDT", "free": "100000", "locked": "0", "total": "100000"}]

    def get_positions(self) -> list[dict[str, Any]]:
        return []

    def get_open_orders(self) -> list[dict[str, Any]]:
        return [order for order in self.orders.values() if order["status"] != "FILLED"]

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
        exchange_order_id = f"mock-{client_order_id}"
        response = {
            "exchange_order_id": exchange_order_id,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side.value,
            "order_type": order_type.value,
            "quantity": str(quantity),
            "price": str(price) if price is not None else None,
            "status": OrderExecutionStatus.FILLED.value,
        }
        self.orders[exchange_order_id] = response
        return response

    def cancel_order(self, *, exchange_order_id: str) -> dict[str, Any]:
        order = self.orders[exchange_order_id]
        order["status"] = OrderExecutionStatus.CANCELLED.value
        return order

    def get_order_status(self, *, exchange_order_id: str) -> dict[str, Any]:
        return self.orders[exchange_order_id]

    def get_symbol_rules(self, *, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "min_quantity": "0.0001", "max_quantity": "100000"}
