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


class CapturingAlertRuntime:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def notify_rate_limit(
        self,
        *,
        exchange_name: str,
        scope: str,
        request_category: str,
        retry_after_seconds: int,
    ) -> tuple[object, ...]:
        self.events.append(
            {
                "exchange_name": exchange_name,
                "scope": scope,
                "request_category": request_category,
                "retry_after_seconds": retry_after_seconds,
            }
        )
        return ()


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


def test_runtime_rate_limiter_alerts_when_repeated_order_is_blocked() -> None:
    clock = ControlledClock()
    alert_runtime = CapturingAlertRuntime()
    limiter = RuntimeRateLimitService(clock=clock, alert_runtime=alert_runtime)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )

    with pytest.raises(RateLimitExceededError):
        limiter.acquire_testnet_order(
            exchange_name=ExchangeName.BINANCE,
            exchange_account_id="acct-1",
            request_path="/api/v3/order",
        )

    assert alert_runtime.events == [
        {
            "exchange_name": "binance",
            "scope": "account",
            "request_category": "order",
            "retry_after_seconds": 1,
        }
    ]


def test_runtime_rate_limiter_alert_omits_account_and_request_path() -> None:
    clock = ControlledClock()
    alert_runtime = CapturingAlertRuntime()
    limiter = RuntimeRateLimitService(clock=clock, alert_runtime=alert_runtime)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-sensitive",
        request_path="/api/v3/order",
    )

    with pytest.raises(RateLimitExceededError):
        limiter.acquire_testnet_order(
            exchange_name=ExchangeName.BINANCE,
            exchange_account_id="acct-sensitive",
            request_path="/api/v3/order",
        )

    event_text = str(alert_runtime.events[0])
    assert "acct-sensitive" not in event_text
    assert "/api/v3/order" not in event_text


def test_runtime_rate_limiter_without_alert_runtime_keeps_existing_behavior() -> None:
    clock = ControlledClock()
    limiter = RuntimeRateLimitService(clock=clock)

    limiter.acquire_testnet_order(
        exchange_name=ExchangeName.BINANCE,
        exchange_account_id="acct-1",
        request_path="/api/v3/order",
    )

    with pytest.raises(RateLimitExceededError):
        limiter.acquire_testnet_order(
            exchange_name=ExchangeName.BINANCE,
            exchange_account_id="acct-1",
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
