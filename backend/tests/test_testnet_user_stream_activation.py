Exit code: 0
Wall time: 1.2 seconds
Output:
from dataclasses import dataclass

import pytest

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials, PreparedExchangeRequest
from app.services.testnet_user_stream import build_testnet_user_stream_connection_plan
from app.services.testnet_user_stream_activation import (
    TestnetUserStreamActivationError,
    activate_testnet_user_stream_connection_plan,
)


@dataclass
class FakeHttpClient:
    response: dict[str, object]
    prepared: PreparedExchangeRequest | None = None

    def execute_prepared_request(
        self,
        prepared: PreparedExchangeRequest,
    ) -> dict[str, object]:
        self.prepared = prepared
        return self.response


def _credentials() -> ExchangeCredentials:
    return ExchangeCredentials(api_key="key", api_secret="secret")


def test_activation_resolves_binance_listen_key_without_exposing_credentials() -> None:
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="account-1",
        exchange_name=ExchangeName.BINANCE,
        credentials=_credentials(),
    )
    client = FakeHttpClient(response={"listenKey": "test-listen-key"})

    activated = activate_testnet_user_stream_connection_plan(plan=plan, http_client=client)

    assert activated.websocket_url == "wss://stream.testnet.binance.vision/ws/test-listen-key"
    assert activated.listen_key_request is None
    assert client.prepared is not None
    assert client.prepared.path == "/api/v3/userDataStream"
    assert "secret" not in str(activated)


def test_activation_rejects_missing_listen_key() -> None:
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="account-1",
        exchange_name=ExchangeName.BINANCE,
        credentials=_credentials(),
    )

    with pytest.raises(TestnetUserStreamActivationError, match="listen key"):
        activate_testnet_user_stream_connection_plan(
            plan=plan,
            http_client=FakeHttpClient(response={}),
        )

