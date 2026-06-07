import json
import time
import urllib.error
import urllib.request
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


def register_and_login(suffix: str) -> str:
    password = "ChangeMe12345!"
    username = f"it_user_{suffix}"
    request(
        "POST",
        "/auth/register",
        {
            "email": f"it_{suffix}@example.com",
            "username": username,
            "password": password,
        },
        expected_status=201,
    )
    token_response = request(
        "POST",
        "/auth/login",
        {"username_or_email": username, "password": password},
    )
    assert isinstance(token_response, dict)
    return str(token_response["access_token"])


def main() -> None:
    wait_for_backend()

    dependencies = request("GET", "/health/dependencies")
    assert dependencies == {"status": "ok", "database": "ok", "redis": "ok"}

    suffix = str(int(time.time()))
    owner_token = register_and_login(suffix)
    other_token = register_and_login(f"{suffix}_other")

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

    accounts = request("GET", "/exchange-accounts", token=owner_token)
    assert isinstance(accounts, list)
    assert any(item["id"] == account_id for item in accounts)

    request(
        "GET",
        f"/exchange-accounts/{account_id}",
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

    print("mock compose integration checks passed")


if __name__ == "__main__":
    main()
