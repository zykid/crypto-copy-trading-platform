from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import PreparedExchangeRequest
from app.services.testnet_http_client import create_testnet_signed_http_client


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[PreparedExchangeRequest] = []

    def request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        self.requests.append(prepared)
        return {"ok": True}


def test_testnet_signed_http_client_uses_binance_testnet_endpoint() -> None:
    client = create_testnet_signed_http_client(exchange_name=ExchangeName.BINANCE)

    prepared = client.prepare_public_request("/api/v3/time")

    assert prepared.url == "https://testnet.binance.vision/api/v3/time"


def test_testnet_signed_http_client_uses_bybit_testnet_endpoint() -> None:
    client = create_testnet_signed_http_client(exchange_name=ExchangeName.BYBIT)

    prepared = client.prepare_public_request("/v5/market/time")

    assert prepared.url == "https://api-testnet.bybit.com/v5/market/time"


def test_testnet_signed_http_client_uses_okx_demo_endpoint() -> None:
    client = create_testnet_signed_http_client(exchange_name=ExchangeName.OKX)

    prepared = client.prepare_public_request("/api/v5/public/time")

    assert prepared.url == "https://openapi.okx.com/api/v5/public/time"


def test_testnet_signed_http_client_accepts_injected_transport_without_network() -> None:
    transport = RecordingTransport()
    client = create_testnet_signed_http_client(
        exchange_name=ExchangeName.BINANCE,
        transport=transport,
    )

    response = client.get_public("/api/v3/time")

    assert response == {"ok": True}
    assert len(transport.requests) == 1
    assert transport.requests[0].url == "https://testnet.binance.vision/api/v3/time"
