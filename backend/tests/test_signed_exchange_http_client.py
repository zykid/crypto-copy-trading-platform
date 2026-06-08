import base64
import hashlib
import hmac
from typing import Any

import pytest

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import (
    ExchangeCredentials,
    ExchangeSecurityType,
    PreparedExchangeRequest,
    SignedExchangeHttpClient,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[PreparedExchangeRequest] = []

    def request(self, prepared: PreparedExchangeRequest) -> dict[str, Any]:
        self.requests.append(prepared)
        return {"ok": True}


def credentials(passphrase: str | None = "test-passphrase") -> ExchangeCredentials:
    return ExchangeCredentials(
        api_key="test-api-key",
        api_secret="test-api-secret",
        passphrase=passphrase,
    )


def hmac_hex(payload: str) -> str:
    return hmac.new(b"test-api-secret", payload.encode("utf-8"), hashlib.sha256).hexdigest()


def hmac_base64(payload: str) -> str:
    digest = hmac.new(b"test-api-secret", payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def test_binance_signed_get_adds_timestamp_recv_window_and_signature() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        timestamp_ms_factory=lambda: 1_700_000_000_000,
    )

    prepared = client.prepare_private_request(
        "/api/v3/account",
        credentials=credentials(),
        params={"symbol": "BTCUSDT"},
    )

    expected_payload = "recvWindow=5000&symbol=BTCUSDT&timestamp=1700000000000"
    assert prepared.method == "GET"
    assert prepared.url == "https://testnet.binance.vision/api/v3/account"
    assert prepared.headers == {"X-MBX-APIKEY": "test-api-key"}
    assert prepared.params["timestamp"] == "1700000000000"
    assert prepared.params["recvWindow"] == "5000"
    assert prepared.params["signature"] == hmac_hex(expected_payload)


def test_bybit_signed_get_uses_v5_header_payload() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BYBIT,
        rest_base_url="https://api-testnet.bybit.com",
        timestamp_ms_factory=lambda: 1_700_000_000_001,
    )

    prepared = client.prepare_private_request(
        "/v5/position/list",
        credentials=credentials(),
        params={"settleCoin": "USDT", "category": "linear"},
    )

    query = "category=linear&settleCoin=USDT"
    expected_payload = f"1700000000001test-api-key5000{query}"
    assert prepared.method == "GET"
    assert prepared.url == "https://api-testnet.bybit.com/v5/position/list"
    assert prepared.params == {"settleCoin": "USDT", "category": "linear"}
    assert prepared.headers["X-BAPI-API-KEY"] == "test-api-key"
    assert prepared.headers["X-BAPI-TIMESTAMP"] == "1700000000001"
    assert prepared.headers["X-BAPI-RECV-WINDOW"] == "5000"
    assert prepared.headers["X-BAPI-SIGN"] == hmac_hex(expected_payload)


def test_okx_demo_signed_get_adds_demo_header_and_base64_signature() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
        iso_timestamp_factory=lambda: "2026-06-08T00:00:00.000Z",
    )

    prepared = client.prepare_private_request(
        "/api/v5/account/positions",
        credentials=credentials(),
        params={"instId": "BTC-USDT"},
        security_type=ExchangeSecurityType.OKX_DEMO_SIGNED,
    )

    expected_payload = (
        "2026-06-08T00:00:00.000ZGET"
        "/api/v5/account/positions?instId=BTC-USDT"
    )
    assert prepared.method == "GET"
    assert prepared.url == "https://openapi.okx.com/api/v5/account/positions"
    assert prepared.headers["OK-ACCESS-KEY"] == "test-api-key"
    assert prepared.headers["OK-ACCESS-TIMESTAMP"] == "2026-06-08T00:00:00.000Z"
    assert prepared.headers["OK-ACCESS-PASSPHRASE"] == "test-passphrase"
    assert prepared.headers["OK-ACCESS-SIGN"] == hmac_base64(expected_payload)
    assert prepared.headers["x-simulated-trading"] == "1"


def test_binance_signed_post_keeps_signed_order_params_in_query() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        timestamp_ms_factory=lambda: 1_700_000_000_003,
    )

    prepared = client.prepare_private_post_request(
        "/api/v3/order",
        credentials=credentials(),
        params={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
        },
    )

    expected_payload = (
        "quantity=0.01&recvWindow=5000&side=BUY&symbol=BTCUSDT"
        "&type=MARKET&timestamp=1700000000003"
    )
    assert prepared.method == "POST"
    assert prepared.body is None
    assert prepared.params["signature"] == hmac_hex(expected_payload)


def test_bybit_signed_post_uses_json_body_payload() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BYBIT,
        rest_base_url="https://api-testnet.bybit.com",
        timestamp_ms_factory=lambda: 1_700_000_000_004,
    )
    body = {
        "symbol": "BTCUSDT",
        "category": "spot",
        "side": "Buy",
        "orderType": "Market",
    }

    prepared = client.prepare_private_post_request(
        "/v5/order/create",
        credentials=credentials(),
        body=body,
    )

    expected_body = (
        '{"category":"spot","orderType":"Market","side":"Buy",'
        '"symbol":"BTCUSDT"}'
    )
    expected_payload = f"1700000000004test-api-key5000{expected_body}"
    assert prepared.method == "POST"
    assert prepared.body == body
    assert prepared.headers["Content-Type"] == "application/json"
    assert prepared.headers["X-BAPI-SIGN"] == hmac_hex(expected_payload)


def test_okx_demo_signed_post_uses_json_body_payload() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
        iso_timestamp_factory=lambda: "2026-06-08T00:00:00.000Z",
    )
    body = {
        "instId": "BTC-USDT",
        "tdMode": "cash",
        "side": "buy",
        "ordType": "market",
    }

    prepared = client.prepare_private_post_request(
        "/api/v5/trade/order",
        credentials=credentials(),
        body=body,
        security_type=ExchangeSecurityType.OKX_DEMO_SIGNED,
    )

    expected_body = (
        '{"instId":"BTC-USDT","ordType":"market","side":"buy",'
        '"tdMode":"cash"}'
    )
    expected_payload = f"2026-06-08T00:00:00.000ZPOST/api/v5/trade/order{expected_body}"
    assert prepared.method == "POST"
    assert prepared.body == body
    assert prepared.headers["Content-Type"] == "application/json"
    assert prepared.headers["x-simulated-trading"] == "1"
    assert prepared.headers["OK-ACCESS-SIGN"] == hmac_base64(expected_payload)


def test_okx_signed_get_requires_passphrase() -> None:
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
    )

    with pytest.raises(ValueError, match="OKX signed requests require an API passphrase"):
        client.prepare_private_request(
            "/api/v5/account/balance",
            credentials=credentials(passphrase=None),
            security_type=ExchangeSecurityType.OKX_DEMO_SIGNED,
        )


def test_signed_client_uses_injected_transport_without_network() -> None:
    transport = RecordingTransport()
    client = SignedExchangeHttpClient(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        transport=transport,
        timestamp_ms_factory=lambda: 1_700_000_000_002,
    )

    response = client.get_private(
        "/api/v3/account",
        credentials=credentials(),
    )

    assert response == {"ok": True}
    assert len(transport.requests) == 1
    assert transport.requests[0].headers == {"X-MBX-APIKEY": "test-api-key"}
