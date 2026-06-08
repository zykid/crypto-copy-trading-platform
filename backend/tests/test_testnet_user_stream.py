import base64
import hashlib
import hmac

import pytest

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials
from app.services.testnet_user_stream import (
    TestnetUserStreamAuthMethod,
    build_testnet_user_stream_connection_plan,
)


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


def test_binance_user_stream_plan_prepares_listen_key_request_without_secret() -> None:
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-1",
        exchange_name=ExchangeName.BINANCE,
        credentials=credentials(),
    )

    assert plan.auth_method == TestnetUserStreamAuthMethod.BINANCE_LISTEN_KEY
    assert plan.websocket_url == "wss://stream.testnet.binance.vision/ws/{listenKey}"
    assert plan.websocket_login_message is None
    assert plan.listen_key_request is not None
    assert plan.listen_key_request.method == "POST"
    assert plan.listen_key_request.url == (
        "https://testnet.binance.vision/api/v3/userDataStream"
    )
    assert plan.listen_key_request.headers == {"X-MBX-APIKEY": "test-api-key"}
    assert "test-api-secret" not in str(plan)


def test_bybit_user_stream_plan_prepares_auth_message_signature_without_secret() -> None:
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-2",
        exchange_name=ExchangeName.BYBIT,
        credentials=credentials(),
        timestamp_ms=1_700_000_000_000,
    )

    expires = "1700000010000"
    assert plan.auth_method == TestnetUserStreamAuthMethod.BYBIT_AUTH
    assert plan.websocket_url == "wss://stream-testnet.bybit.com/v5/private"
    assert plan.listen_key_request is None
    assert plan.websocket_login_message == {
        "op": "auth",
        "args": ["test-api-key", expires, hmac_hex(f"GET/realtime{expires}")],
    }
    assert "test-api-secret" not in str(plan)


def test_okx_user_stream_plan_prepares_login_message_signature_without_secret() -> None:
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id="acct-3",
        exchange_name=ExchangeName.OKX,
        credentials=credentials(),
        unix_timestamp="1700000000",
    )

    expected_sign = hmac_base64("1700000000GET/users/self/verify")
    assert plan.auth_method == TestnetUserStreamAuthMethod.OKX_LOGIN
    assert plan.websocket_url == "wss://wspap.okx.com:8443/ws/v5/private"
    assert plan.listen_key_request is None
    assert plan.websocket_login_message == {
        "op": "login",
        "args": [
            {
                "apiKey": "test-api-key",
                "passphrase": "test-passphrase",
                "timestamp": "1700000000",
                "sign": expected_sign,
            }
        ],
    }
    assert "test-api-secret" not in str(plan)


def test_okx_user_stream_plan_requires_passphrase() -> None:
    with pytest.raises(ValueError, match="OKX WebSocket login requires an API passphrase"):
        build_testnet_user_stream_connection_plan(
            exchange_account_id="acct-3",
            exchange_name=ExchangeName.OKX,
            credentials=credentials(passphrase=None),
        )
