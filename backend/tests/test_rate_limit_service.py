import pytest

from app.db.models.exchange_account import ExchangeName
from app.services.rate_limit_service import RateLimitExceededError, RuntimeRateLimitService


class ControlledClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_runtime_rate_limiter_blocks_repeated_testnet_order_in_same_window() -> None:
    clock = ControlledClock()
    limiter = RuntimeRateLimitService(clock=clock)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.acquire_testnet_order(
            exchange_name=ExchangeName.BINANCE,
            exchange_account_id="acct-1",
            request_path="/api/v3/order",
        )

    assert exc_info.value.rule_name == "TESTNET_ORDER_ACCOUNT_SAFETY"
    assert exc_info.value.retry_after_seconds == 1


def test_runtime_rate_limiter_resets_after_window_expires() -> None:
    clock = ControlledClock()
    limiter = RuntimeRateLimitService(clock=clock)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )
    clock.advance(1.0)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )


def test_runtime_rate_limiter_is_scoped_per_exchange_account_for_safety_rule() -> None:
    clock = ControlledClock()
    limiter = RuntimeRateLimitService(clock=clock)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )
    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-2",
        request_path="/api/v3/order",
    )
