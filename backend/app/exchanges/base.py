from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.db.models.trading import OrderSide, OrderType


class ExchangeAdapter(ABC):
    @abstractmethod
    def get_server_time(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_exchange_info(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_balances(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_open_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, *, exchange_order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, *, exchange_order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_symbol_rules(self, *, symbol: str) -> dict[str, Any]:
        raise NotImplementedError
