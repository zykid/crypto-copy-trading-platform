import pytest

from app.db.models.exchange_account import ExchangeName
from app.services.rate_limit_service import (
    RateLimitExceededError,
    RedisRateLimitWindowStore,
    RuntimeRateLimitService,
)


class ControlledClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def incr(self, key: str) -> int:
        value = self.values.get(key, 0) + 1
        self.values[key] = value
        return value

    def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True

    def ttl(self, key: str) -> int:
        return self.expirations.get(key, -1)


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


def test_redis_rate_limit_store_sets_ttl_for_new_window() -> None:
    redis = FakeRedis()
    store = RedisRateLimitWindowStore(redis)  # type: ignore[arg-type]

    window = store.acquire(
        key=("binance", "TESTNET_ORDER_ACCOUNT_SAFETY", "acct-1:/api/v3/order"),
        limit=1,
        interval_seconds=1,
        now=1_000.0,
    )

    redis_key = "trading:rate_limit:binance:TESTNET_ORDER_ACCOUNT_SAFETY:acct-1__api_v3_order"
    assert window.count == 1
    assert window.retry_after_seconds == 1
    assert redis.values[redis_key] == 1
    assert redis.expirations[redis_key] == 1


def test_runtime_rate_limiter_can_use_redis_window_store() -> None:
    redis = FakeRedis()
    limiter = RuntimeRateLimitService(
        store=RedisRateLimitWindowStore(redis),  # type: ignore[arg-type]
    )

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
