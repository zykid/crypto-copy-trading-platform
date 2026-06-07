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
) -> dict[str, Any] | list[dict[str, Any]] | None:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

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

    secret_metadata = request(
        "POST",
        f"/exchange-accounts/{account_id}/api-key",
        {
            "api_key": "mock-key",
            "api_secret": "mock-secret-never-return",
            "passphrase": "mock-passphrase",
        },
        token=owner_token,
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

    preview = request(
        "POST",
        f"/positions/{account_id}/target-preview?symbol=BTCUSDT&target_quantity=1.0",
        token=owner_token,
    )
    assert isinstance(preview, dict)
    assert preview["symbol"] == "BTCUSDT"
    assert_decimal(preview["current_quantity"], "0")
    assert_decimal(preview["target_quantity"], "1.0")
    assert_decimal(preview["delta_quantity"], "1.0")
    assert preview["side"] == "BUY"

    signal = request(
        "POST",
        "/signals/manual",
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "0.1",
        },
        token=owner_token,
        expected_status=201,
    )
    assert isinstance(signal, dict)
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

    print("mock compose integration checks passed")


if __name__ == "__main__":
    main()
