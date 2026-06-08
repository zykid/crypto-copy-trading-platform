from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import OrderSide, OrderType
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeSecurityType,
    PreparedExchangeRequest,
    SignedExchangeHttpClient,
)
from app.services.testnet_order_gate import TestnetOrderGateResult


@dataclass(frozen=True)
class TestnetOrderRequestInput:
    exchange_name: ExchangeName
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    client_order_id: str
    price: Decimal | None = None


class TestnetOrderRequestBlockedError(RuntimeError):
    pass


def prepare_testnet_order_request(
    *,
    order: TestnetOrderRequestInput,
    gate_result: TestnetOrderGateResult,
    http_client: SignedExchangeHttpClient,
    credentials: ExchangeCredentials,
) -> PreparedExchangeRequest:
    if not gate_result.approved:
        raise TestnetOrderRequestBlockedError(
            "testnet order request preparation is blocked by the preflight gate"
        )
    if order.exchange_name == ExchangeName.BINANCE:
        return http_client.prepare_private_post_request(
            "/api/v3/order",
            credentials=credentials,
            params=_binance_order_params(order),
        )
    if order.exchange_name == ExchangeName.BYBIT:
        return http_client.prepare_private_post_request(
            "/v5/order/create",
            credentials=credentials,
            body=_bybit_order_body(order),
        )
    if order.exchange_name == ExchangeName.OKX:
        return http_client.prepare_private_post_request(
            "/api/v5/trade/order",
            credentials=credentials,
            body=_okx_order_body(order),
            security_type=ExchangeSecurityType.OKX_DEMO_SIGNED,
        )
    raise ValueError(f"unsupported testnet order exchange: {order.exchange_name}")


def _binance_order_params(order: TestnetOrderRequestInput) -> dict[str, str]:
    params = {
        "symbol": order.symbol.upper(),
        "side": order.side.value,
        "type": order.order_type.value,
        "quantity": _decimal_text(order.quantity),
        "newClientOrderId": order.client_order_id,
    }
    if order.order_type == OrderType.LIMIT:
        params["timeInForce"] = "GTC"
        params["price"] = _required_price(order)
    return params


def _bybit_order_body(order: TestnetOrderRequestInput) -> dict[str, Any]:
    body: dict[str, Any] = {
        "category": "spot",
        "symbol": order.symbol.upper(),
        "side": _title_side(order.side),
        "orderType": _title_order_type(order.order_type),
        "qty": _decimal_text(order.quantity),
        "orderLinkId": order.client_order_id,
    }
    if order.order_type == OrderType.LIMIT:
        body["price"] = _required_price(order)
    return body


def _okx_order_body(order: TestnetOrderRequestInput) -> dict[str, Any]:
    body: dict[str, Any] = {
        "instId": _okx_symbol(order.symbol),
        "tdMode": "cash",
        "side": order.side.value.lower(),
        "ordType": order.order_type.value.lower(),
        "sz": _decimal_text(order.quantity),
        "clOrdId": order.client_order_id,
    }
    if order.order_type == OrderType.LIMIT:
        body["px"] = _required_price(order)
    return body


def _required_price(order: TestnetOrderRequestInput) -> str:
    if order.price is None:
        raise ValueError("limit orders require price")
    return _decimal_text(order.price)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _title_side(side: OrderSide) -> str:
    return "Buy" if side == OrderSide.BUY else "Sell"


def _title_order_type(order_type: OrderType) -> str:
    return "Market" if order_type == OrderType.MARKET else "Limit"


def _okx_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if "-" in normalized:
        return normalized
    if normalized.endswith("USDT"):
        return f"{normalized[:-4]}-USDT"
    return normalized
