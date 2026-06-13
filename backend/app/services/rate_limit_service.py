from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from redis import Redis

from app.db.models.exchange_account import ExchangeName
from app.exchanges.rate_limit import RateLimitScope, get_exchange_rate_limit_config


@dataclass
class _WindowState:
    started_at: float
    count: int


@dataclass(frozen=True)
class RuntimeRateLimitRule:
    name: str
    scope: RateLimitScope
    limit: int
    interval_seconds: int


@dataclass(frozen=True)
class RateLimitWindow:
    count: int
    retry_after_seconds: int


class RateLimitExceededError(RuntimeError):
    def __init__(self, *, rule_name: str, retry_after_seconds: int) -> None:
        super().__init__("runtime rate limit exceeded")
        self.rule_name = rule_name
        self.retry_after_seconds = retry_after_seconds


class RateLimitAlertRuntime(Protocol):
    def notify_rate_limit(
        self,
        *,
        exchange_name: str,
        scope: str,
        request_category: str,
        retry_after_seconds: int,
    ) -> tuple[object, ...]: ...


class RateLimitWindowStore(Protocol):
    def acquire(
        self,
        *,
        key: tuple[str, str, str],
        limit: int,
        interval_seconds: int,
        now: float,
    ) -> RateLimitWindow: ...


class InMemoryRateLimitWindowStore:
    def __init__(self) -> None:
        self._windows: dict[tuple[str, str, str], _WindowState] = {}

    def acquire(
        self,
        *,
        key: tuple[str, str, str],
        limit: int,
        interval_seconds: int,
        now: float,
    ) -> RateLimitWindow:
        window = self._active_window(key=key, now=now, interval_seconds=interval_seconds)
        window.count += 1
        return RateLimitWindow(
            count=window.count,
            retry_after_seconds=_retry_after_seconds(
                now=now,
                started_at=window.started_at,
                interval_seconds=interval_seconds,
            ),
        )

    def _active_window(
        self,
        *,
        key: tuple[str, str, str],
        now: float,
        interval_seconds: int,
    ) -> _WindowState:
        window = self._windows.get(key)
        if window is None or now - window.started_at >= interval_seconds:
            window = _WindowState(started_at=now, count=0)
            self._windows[key] = window
        return window


class RedisRateLimitWindowStore:
    def __init__(self, redis: Redis, *, key_prefix: str = "trading:rate_limit") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def acquire(
        self,
        *,
        key: tuple[str, str, str],
        limit: int,
        interval_seconds: int,
        now: float,
    ) -> RateLimitWindow:
        redis_key = self._redis_key(key)
        count = int(self._redis.incr(redis_key))
        if count == 1:
            self._redis.expire(redis_key, interval_seconds)
        ttl = self._redis.ttl(redis_key)
        retry_after_seconds = max(1, int(ttl if ttl and ttl > 0 else interval_seconds))
        return RateLimitWindow(count=count, retry_after_seconds=retry_after_seconds)

    def _redis_key(self, key: tuple[str, str, str]) -> str:
        return ":".join((self._key_prefix, *(_escape_key_part(part) for part in key)))


class RuntimeRateLimitService:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        store: RateLimitWindowStore | None = None,
        alert_runtime: RateLimitAlertRuntime | None = None,
    ) -> None:
        self._clock = clock
        self._store = store or InMemoryRateLimitWindowStore()
        self._alert_runtime = alert_runtime

    def acquire_testnet_order(
        self,
        *,
        exchange_name: ExchangeName,
        exchange_account_id: str,
        request_path: str,
    ) -> None:
        rules = _testnet_order_rules(exchange_name)
        now = self._clock()
        keys = [
            _rate_limit_key(
                rule=rule,
                exchange_name=exchange_name,
                exchange_account_id=exchange_account_id,
                request_path=request_path,
            )
            for rule in rules
        ]

        for rule, key in zip(rules, keys, strict=True):
            window = self._store.acquire(
                key=key,
                limit=rule.limit,
                interval_seconds=rule.interval_seconds,
                now=now,
            )
            if window.count > rule.limit:
                self._notify_rate_limit_blocked(
                    exchange_name=exchange_name,
                    rule=rule,
                    retry_after_seconds=window.retry_after_seconds,
                )
                raise RateLimitExceededError(
                    rule_name=rule.name,
                    retry_after_seconds=window.retry_after_seconds,
                )

    def _notify_rate_limit_blocked(
        self,
        *,
        exchange_name: ExchangeName,
        rule: RuntimeRateLimitRule,
        retry_after_seconds: int,
    ) -> None:
        if self._alert_runtime is None:
            return
        self._alert_runtime.notify_rate_limit(
            exchange_name=exchange_name.value,
            scope=_safe_alert_scope(rule.scope),
            request_category="order",
            retry_after_seconds=retry_after_seconds,
        )


def _testnet_order_rules(exchange_name: ExchangeName) -> tuple[RuntimeRateLimitRule, ...]:
    rules = [
        RuntimeRateLimitRule(
            name="TESTNET_ORDER_ACCOUNT_SAFETY",
            scope=RateLimitScope.ACCOUNT,
            limit=1,
            interval_seconds=1,
        )
    ]
    config = get_exchange_rate_limit_config(exchange_name)
    for rule in config.rules:
        if rule.limit is None or rule.interval_seconds is None or "REST" not in rule.applies_to:
            continue
        rules.append(
            RuntimeRateLimitRule(
                name=rule.name,
                scope=rule.scope,
                limit=rule.limit,
                interval_seconds=rule.interval_seconds,
            )
        )
    return tuple(rules)


def _rate_limit_key(
    *,
    rule: RuntimeRateLimitRule,
    exchange_name: ExchangeName,
    exchange_account_id: str,
    request_path: str,
) -> tuple[str, str, str]:
    scope_key = "global" if rule.scope == RateLimitScope.IP else exchange_account_id
    return (exchange_name.value, rule.name, f"{scope_key}:{request_path}")


def _retry_after_seconds(*, now: float, started_at: float, interval_seconds: int) -> int:
    remaining = interval_seconds - int(now - started_at)
    return max(1, remaining)


def _safe_alert_scope(scope: RateLimitScope) -> str:
    if scope == RateLimitScope.IP:
        return "ip"
    if scope == RateLimitScope.ACCOUNT:
        return "account"
    return "global"


def _escape_key_part(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


runtime_rate_limit_service = RuntimeRateLimitService()
