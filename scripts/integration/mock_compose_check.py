import json
import time
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

BASE_URL = "http://localhost:8000/api/v1"


def request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    expected_status: int = 200,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers is not None:
        headers.update(extra_headers)

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        status_code = exc.code

    if status_code != expected_status:
        raise AssertionError(
            f"{method} {path} returned {status_code}, expected {expected_status}: {body}"
        )
    return None if body == "" else json.loads(body)


def assert_decimal(value: object, expected: str) -> None:
    actual_decimal = Decimal(str(value))
    expected_decimal = Decimal(expected)
    if actual_decimal != expected_decimal:
        raise AssertionError(f"expected decimal {expected_decimal}, got {actual_decimal}")


def wait_for_backend() -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            health = request("GET", "/health")
            if isinstance(health, dict) and health.get("status") == "ok":
                return
        except Exception:
            time.sleep(2)
    raise TimeoutError("backend did not become healthy")


def register_user(suffix: str) -> dict[str, Any]:
    user = request(
        "POST",
        "/auth/register",
        {
            "email": f"it_{suffix}@example.com",
            "username": f"it_user_{suffix}",
            "password": "ChangeMe12345!",
        },
        expected_status=201,
    )
    assert isinstance(user, dict)
    return user


def login_user(suffix: str) -> str:
    token_response = request(
        "POST",
        "/auth/login",
        {"username_or_email": f"it_user_{suffix}", "password": "ChangeMe12345!"},
    )
    assert isinstance(token_response, dict)
    return str(token_response["access_token"])


def register_and_login(suffix: str) -> tuple[dict[str, Any], str]:
    user = register_user(suffix)
    token = login_user(suffix)
    return user, token


def reauthenticate_user(token: str) -> str:
    response = request(
        "POST",
        "/auth/reauthenticate",
        {"password": "ChangeMe12345!"},
        token=token,
    )
    assert isinstance(response, dict)
    return str(response["reauthentication_token"])


def create_manual_signal(
    token: str,
    *,
    symbol: str,
    side: str,
    quantity: str | None = None,
    target_position_quantity: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "order_type": "MARKET",
    }
    if quantity is not None:
        payload["quantity"] = quantity
    if target_position_quantity is not None:
        payload["target_position_quantity"] = target_position_quantity
    signal = request(
        "POST",
        "/signals/manual",
        payload,
        token=token,
        expected_status=201,
    )
    assert isinstance(signal, dict)
    return signal


def preview_position(
    token: str,
    *,
    account_id: str,
    symbol: str,
    target_quantity: str,
) -> dict[str, Any]:
    preview = request(
        "POST",
        f"/positions/{account_id}/target-preview?symbol={symbol}&target_quantity={target_quantity}",
        token=token,
    )
    assert isinstance(preview, dict)
    return preview


def main() -> None:
    wait_for_backend()

    dependencies = request("GET", "/health/dependencies")
    assert dependencies == {"status": "ok", "database": "ok", "redis": "ok"}

    suffix = str(int(time.time()))
    owner, owner_token = register_and_login(suffix)
    other, other_token = register_and_login(f"{suffix}_other")

    request(
        "POST",
        "/auth/register",
        {
            "email": owner["email"],
            "username": f"it_user_{suffix}_duplicate_email",
            "password": "ChangeMe12345!",
        },
        expected_status=409,
    )
    request(
        "POST",
        "/auth/register",
        {
            "email": f"it_{suffix}_duplicate_username@example.com",
            "username": owner["username"],
            "password": "ChangeMe12345!",
        },
        expected_status=409,
    )

    account = request(
        "POST",
        "/exchange-accounts",
        {
            "exchange_name": "mock",
            "account_label": "Mock Simulation",
            "account_mode": "SIMULATION",
            "trading_enabled": True,
        },
        token=owner_token,
        expected_status=201,
    )
    assert isinstance(account, dict)
    account_id = str(account["id"])

    persisted_account = request("GET", f"/exchange-accounts/{account_id}", token=owner_token)
    assert isinstance(persisted_account, dict)
    assert persisted_account["id"] == account_id
    assert persisted_account["user_id"] == owner["id"]

    accounts = request("GET", "/exchange-accounts", token=owner_token)
    assert isinstance(accounts, list)
    assert any(item["id"] == account_id for item in accounts)

    request(
        "GET",
        f"/exchange-accounts/{account_id}",
        token=other_token,
        expected_status=404,
    )

    permission = request(
        "POST",
        "/permissions",
        {"grantee_user_id": other["id"], "view_only": True},
        token=owner_token,
        expected_status=201,
    )
    assert isinstance(permission, dict)
    assert permission["owner_user_id"] == owner["id"]
    assert permission["grantee_user_id"] == other["id"]
    assert permission["view_only"] is True
    assert permission["trade_manual"] is False

    request(
        "PATCH",
        f"/permissions/{permission['id']}",
        {"trade_manual": True},
        token=other_token,
        expected_status=404,
    )

    reauthentication_token = reauthenticate_user(owner_token)
    secret_metadata = request(
        "POST",
        f"/exchange-accounts/{account_id}/api-key",
        {
            "api_key": "mock-key",
            "api_secret": "mock-secret-never-return",
            "passphrase": "mock-passphrase",
        },
        token=owner_token,
        extra_headers={
            "X-Reauthentication-Token": reauthentication_token,
        },
    )
    assert isinstance(secret_metadata, dict)
    assert secret_metadata["configured"] is True
    assert "api_secret" not in secret_metadata
    assert "mock-secret-never-return" not in json.dumps(secret_metadata)

    persisted_secret_metadata = request(
        "GET",
        f"/exchange-accounts/{account_id}/api-key",
        token=owner_token,
    )
    assert isinstance(persisted_secret_metadata, dict)
    assert persisted_secret_metadata == secret_metadata

    preview = preview_position(
        owner_token,
        account_id=account_id,
        symbol="BTCUSDT",
        target_quantity="1.0",
    )
    assert preview["symbol"] == "BTCUSDT"
    assert_decimal(preview["current_quantity"], "0")
    assert_decimal(preview["target_quantity"], "1.0")
    assert_decimal(preview["delta_quantity"], "1.0")
    assert preview["side"] == "BUY"

    signal = create_manual_signal(
        owner_token,
        symbol="BTCUSDT",
        side="BUY",
        quantity="0.1",
    )
    signal_id = str(signal["id"])

    execution = request(
        "POST",
        f"/orders/execute-signal/{signal_id}",
        {"exchange_account_id": account_id},
        token=owner_token,
    )
    assert isinstance(execution, dict)
    assert execution["status"] == "FAILED"
    assert execution["risk_result"]["decision"] == "REJECTED"
    assert "risk settings trading is disabled" in execution["risk_result"]["reasons"]

    duplicate_execution = request(
        "POST",
        f"/orders/execute-signal/{signal_id}",
        {"exchange_account_id": account_id},
        token=owner_token,
    )
    assert isinstance(duplicate_execution, dict)
    assert duplicate_execution["execution_id"] == execution["execution_id"]
    assert duplicate_execution["client_order_id"] == execution["client_order_id"]

    request(
        "POST",
        f"/orders/execute-signal/{signal_id}",
        {"exchange_account_id": account_id},
        token=other_token,
        expected_status=404,
    )

    risk_settings = request(
        "PATCH",
        f"/risk-settings/{account_id}",
        {
            "trading_enabled": True,
            "min_order_quantity": "0.01",
            "max_order_quantity": "1",
            "max_single_order_notional": "1000",
        },
        token=owner_token,
    )
    assert isinstance(risk_settings, dict)
    assert risk_settings["trading_enabled"] is True
    assert risk_settings["exchange_account_id"] == account_id

    fill_signal = create_manual_signal(
        owner_token,
        symbol="BTCUSDT",
        side="BUY",
        quantity="0.2",
    )
    fill_execution = request(
        "POST",
        f"/orders/execute-signal/{fill_signal['id']}",
        {"exchange_account_id": account_id},
        token=owner_token,
    )
    assert isinstance(fill_execution, dict)
    assert fill_execution["status"] == "FILLED"
    assert fill_execution["risk_result"]["decision"] == "PASSED"
    assert_decimal(fill_execution["quantity"], "0.2")

    post_fill_preview = preview_position(
        owner_token,
        account_id=account_id,
        symbol="BTCUSDT",
        target_quantity="0.2",
    )
    assert_decimal(post_fill_preview["current_quantity"], "0.2")
    assert_decimal(post_fill_preview["target_quantity"], "0.2")
    assert_decimal(post_fill_preview["delta_quantity"], "0")
    assert post_fill_preview["side"] is None

    target_signal = create_manual_signal(
        owner_token,
        symbol="BTCUSDT",
        side="BUY",
        target_position_quantity="0.5",
    )
    target_execution = request(
        "POST",
        f"/orders/execute-signal/{target_signal['id']}",
        {"exchange_account_id": account_id},
        token=owner_token,
    )
    assert isinstance(target_execution, dict)
    assert target_execution["status"] == "FILLED"
    assert_decimal(target_execution["quantity"], "0.3")

    post_target_preview = preview_position(
        owner_token,
        account_id=account_id,
        symbol="BTCUSDT",
        target_quantity="0.5",
    )
    assert_decimal(post_target_preview["current_quantity"], "0.5")
    assert_decimal(post_target_preview["target_quantity"], "0.5")
    assert_decimal(post_target_preview["delta_quantity"], "0")
    assert post_target_preview["side"] is None

    print("mock compose integration checks passed")


if __name__ == "__main__":
    main()
