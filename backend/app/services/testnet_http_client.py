from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeHttpTransport, SignedExchangeHttpClient
from app.exchanges.testnet_config import get_testnet_endpoint_config


def create_testnet_signed_http_client(
    *,
    exchange_name: ExchangeName,
    transport: ExchangeHttpTransport | None = None,
) -> SignedExchangeHttpClient:
    endpoint_config = get_testnet_endpoint_config(exchange_name)
    return SignedExchangeHttpClient(
        exchange_name=exchange_name,
        rest_base_url=endpoint_config.rest_base_url,
        transport=transport,
    )
