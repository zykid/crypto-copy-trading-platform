from dataclasses import dataclass
from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import ExchangeCredentials, SignedExchangeHttpClient
from app.services.rate_limit_service import RuntimeRateLimitService
from app.services.testnet_order_gate import TestnetOrderGateResult
from app.services.testnet_order_request import (
    TestnetOrderRequestInput,
    prepare_testnet_order_request,
)


@dataclass(frozen=True)
class TestnetOrderExecutionResult:
    exchange_name: ExchangeName
    client_order_id: str
    request_method: str
    request_path: str
    exchange_response: dict[str, Any]


def execute_testnet_order(
    *,
    order: TestnetOrderRequestInput,
    gate_result: TestnetOrderGateResult,
    http_client: SignedExchangeHttpClient,
    credentials: ExchangeCredentials,
    rate_limiter: RuntimeRateLimitService | None = None,
    exchange_account_id: str | None = None,
) -> TestnetOrderExecutionResult:
    prepared = prepare_testnet_order_request(
        order=order,
        gate_result=gate_result,
        http_client=http_client,
        credentials=credentials,
    )
    if rate_limiter is not None:
        if exchange_account_id is None:
            raise RuntimeError("exchange account id is required for rate limit enforcement")
        rate_limiter.acquire_testnet_order(
            exchange_name=order.exchange_name,
            exchange_account_id=exchange_account_id,
            request_path=prepared.path,
        )
    exchange_response = http_client.execute_prepared_request(prepared)
    return TestnetOrderExecutionResult(
        exchange_name=order.exchange_name,
        client_order_id=order.client_order_id,
        request_method=prepared.method,
        request_path=prepared.path,
        exchange_response=exchange_response,
    )
