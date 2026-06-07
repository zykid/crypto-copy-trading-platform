from app.db.models.exchange_account import ExchangeName
from app.exchanges.read_only import ReadOnlyTestnetAdapter
from app.exchanges.testnet_config import get_testnet_endpoint_config


class BinanceAdapter(ReadOnlyTestnetAdapter):
    def __init__(self, *, adapters_enabled: bool = False) -> None:
        super().__init__(
            endpoint_config=get_testnet_endpoint_config(ExchangeName.BINANCE),
            adapters_enabled=adapters_enabled,
        )
