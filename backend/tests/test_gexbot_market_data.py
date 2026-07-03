from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import settings
from app.main import app
from app.services.gexbot_market_data import (
    GexbotConfigurationError,
    GexbotMarketDataClient,
    GexbotValidationError,
)


class RecordingGexbotTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"ok": True}


def test_gexbot_tickers_do_not_require_authorization_header() -> None:
    transport = RecordingGexbotTransport()
    client = GexbotMarketDataClient(
        base_url="https://api.gex.bot/v2/",
        transport=transport,
    )

    result = client.list_tickers()

    assert result == {"ok": True}
    assert transport.requests[0]["url"] == "https://api.gex.bot/v2/tickers"
    assert "Authorization" not in transport.requests[0]["headers"]


def test_gexbot_private_request_adds_bearer_custom_prefix() -> None:
    transport = RecordingGexbotTransport()
    client = GexbotMarketDataClient(
        base_url="https://api.gex.bot/v2",
        api_key="secret-value",
        timeout_seconds=2.5,
        transport=transport,
    )

    client.get_package_category(ticker="spx", package="classic", category="gex_full")

    request = transport.requests[0]
    assert request["url"] == "https://api.gex.bot/v2/SPX/classic/gex_full"
    assert request["headers"]["Authorization"] == "Bearer gexbot_custom_secret-value"
    assert request["timeout_seconds"] == 2.5


def test_gexbot_private_request_accepts_prefixed_bearer_token() -> None:
    transport = RecordingGexbotTransport()
    client = GexbotMarketDataClient(
        base_url="https://api.gex.bot/v2",
        api_key="Bearer gexbot_custom_existing",
        transport=transport,
    )

    client.get_orderflow(ticker="ES")

    assert transport.requests[0]["url"] == "https://api.gex.bot/v2/ES/orderflow/orderflow"
    assert transport.requests[0]["headers"]["Authorization"] == "Bearer gexbot_custom_existing"


def test_gexbot_private_request_fails_closed_without_api_key() -> None:
    client = GexbotMarketDataClient(base_url="https://api.gex.bot/v2")

    with pytest.raises(GexbotConfigurationError):
        client.get_package_category(ticker="SPX", package="classic", category="gex_full")


def test_gexbot_rejects_invalid_path_segments() -> None:
    client = GexbotMarketDataClient(
        base_url="https://api.gex.bot/v2",
        api_key="secret-value",
    )

    with pytest.raises(GexbotValidationError):
        client.get_package_category(ticker="../SPX", package="classic", category="gex_full")
    with pytest.raises(GexbotValidationError):
        client.get_package_category(ticker="SPX", package="quant", category="gex_full")
    with pytest.raises(GexbotValidationError):
        client.get_package_category(ticker="SPX", package="classic", category="../secret")


def test_market_data_provider_route_requires_authenticated_user() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/market-data/providers")

    assert response.status_code == 401


def test_market_data_provider_route_returns_safe_provider_metadata() -> None:
    def fake_user() -> object:
        return object()

    old_key = settings.gexbot_api_key
    settings.gexbot_api_key = "super-secret"
    app.dependency_overrides[get_current_user] = fake_user
    client = TestClient(app)
    try:
        response = client.get("/api/v1/market-data/providers")
    finally:
        app.dependency_overrides.clear()
        settings.gexbot_api_key = old_key

    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"][0]["id"] == "gexbot"
    assert payload["providers"][0]["configured"] is True
    assert "super-secret" not in str(payload)
