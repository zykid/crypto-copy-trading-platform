from app.db.models.exchange_account import ExchangeName
from app.exchanges.base import ExchangeAdapter
from app.exchanges.binance import BinanceAdapter
from app.exchanges.bybit import BybitAdapter
from app.exchanges.mock import MockExchange
from app.exchanges.okx import OKXAdapter


def create_exchange_adapter(
    exchange_name: ExchangeName,
    *,
    testnet_adapters_enabled: bool = False,
) -> ExchangeAdapter:
    if exchange_name == ExchangeName.MOCK:
        return MockExchange()
    if exchange_name == ExchangeName.BINANCE:
        return BinanceAdapter(adapters_enabled=testnet_adapters_enabled)
    if exchange_name == ExchangeName.BYBIT:
        return BybitAdapter(adapters_enabled=testnet_adapters_enabled)
    if exchange_name == ExchangeName.OKX:
        return OKXAdapter(adapters_enabled=testnet_adapters_enabled)
    raise ValueError(f"unsupported exchange: {exchange_name}")
