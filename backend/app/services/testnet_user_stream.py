import base64
import hashlib
import hmac
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials, PreparedExchangeRequest
from app.exchanges.testnet_config import get_testnet_endpoint_config


class TestnetUserStreamAuthMethod(StrEnum):
    BINANCE_LISTEN_KEY = "BINANCE_LISTEN_KEY"
    BYBIT_AUTH = "BYBIT_AUTH"
    OKX_LOGIN = "OKX_LOGIN"


@dataclass(frozen=True)
class TestnetUserStreamConnectionPlan:
    exchange_account_id: str
    exchange_name: ExchangeName
    websocket_url: str
    auth_method: TestnetUserStreamAuthMethod
    listen_key_request: PreparedExchangeRequest | None = None
    websocket_login_message: dict[str, Any] | None = None


class TestnetUserStreamNotSupportedError(RuntimeError):
    pass


def build_testnet_user_stream_connection_plan(
    *,
    exchange_account_id: str,
    exchange_name: ExchangeName,
    credentials: ExchangeCredentials,
    timestamp_ms: int = 1_700_000_000_000,
    unix_timestamp: str = "1700000000",
) -> TestnetUserStreamConnectionPlan:
    endpoint = get_testnet_endpoint_config(exchange_name)
    if exchange_name == ExchangeName.BINANCE:
        if endpoint.public_ws_url is None:
            raise TestnetUserStreamNotSupportedError("Binance user stream endpoint is not configured")
        return TestnetUserStreamConnectionPlan(
            exchange_account_id=exchange_account_id,
            exchange_name=exchange_name,
            websocket_url=f"{endpoint.public_ws_url}/{{listenKey}}",
            auth_method=TestnetUserStreamAuthMethod.BINANCE_LISTEN_KEY,
            listen_key_request=PreparedExchangeRequest(
                method="POST",
                url=f"{endpoint.rest_base_url}/api/v3/userDataStream",
                path="/api/v3/userDataStream",
                params={},
                headers={"X-MBX-APIKEY": credentials.api_key},
            ),
        )
    if exchange_name == ExchangeName.BYBIT:
        if endpoint.private_ws_url is None:
            raise TestnetUserStreamNotSupportedError("Bybit private WebSocket endpoint is not configured")
        expires = str(timestamp_ms + 10_000)
        return TestnetUserStreamConnectionPlan(
            exchange_account_id=exchange_account_id,
            exchange_name=exchange_name,
            websocket_url=endpoint.private_ws_url,
            auth_method=TestnetUserStreamAuthMethod.BYBIT_AUTH,
            websocket_login_message={
                "op": "auth",
                "args": [
                    credentials.api_key,
                    expires,
                    _hmac_sha256_hex(credentials.api_secret, f"GET/realtime{expires}"),
                ],
            },
        )
    if exchange_name == ExchangeName.OKX:
        if endpoint.private_ws_url is None:
            raise TestnetUserStreamNotSupportedError("OKX private WebSocket endpoint is not configured")
        if credentials.passphrase is None:
            raise ValueError("OKX WebSocket login requires an API passphrase")
        sign = _hmac_sha256_base64(
            credentials.api_secret,
            f"{unix_timestamp}GET/users/self/verify",
        )
        return TestnetUserStreamConnectionPlan(
            exchange_account_id=exchange_account_id,
            exchange_name=exchange_name,
            websocket_url=endpoint.private_ws_url,
            auth_method=TestnetUserStreamAuthMethod.OKX_LOGIN,
            websocket_login_message={
                "op": "login",
                "args": [
                    {
                        "apiKey": credentials.api_key,
                        "passphrase": credentials.passphrase,
                        "timestamp": unix_timestamp,
                        "sign": sign,
                    }
                ],
            },
        )
    raise TestnetUserStreamNotSupportedError(
        f"testnet user stream is not supported for {exchange_name}"
    )


def _hmac_sha256_hex(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _hmac_sha256_base64(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")
