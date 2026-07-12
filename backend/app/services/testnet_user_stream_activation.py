Exit code: 0
Wall time: 3.2 seconds
Output:
from dataclasses import replace
from typing import Any

from app.services.testnet_user_stream import TestnetUserStreamConnectionPlan


class TestnetUserStreamActivationError(RuntimeError):
    pass


def activate_testnet_user_stream_connection_plan(
    *,
    plan: TestnetUserStreamConnectionPlan,
    http_client: Any,
) -> TestnetUserStreamConnectionPlan:
    """Resolve a Binance listen key for one explicitly requested stream session."""
    request = plan.listen_key_request
    if request is None:
        return plan
    response = http_client.execute_prepared_request(request)
    listen_key = _listen_key(response)
    websocket_url = plan.websocket_url.replace("{listenKey}", listen_key)
    if "{" in websocket_url or "}" in websocket_url:
        raise TestnetUserStreamActivationError("testnet user stream URL is invalid")
    return replace(
        plan,
        websocket_url=websocket_url,
        listen_key_request=None,
    )


def _listen_key(response: object) -> str:
    payload = response if isinstance(response, dict) else {}
    value = payload.get("listenKey")
    if not isinstance(value, str):
        raise TestnetUserStreamActivationError("testnet user stream listen key is missing")
    listen_key = value.strip()
    if not listen_key or len(listen_key) > 256 or "/" in listen_key:
        raise TestnetUserStreamActivationError("testnet user stream listen key is invalid")
    return listen_key

