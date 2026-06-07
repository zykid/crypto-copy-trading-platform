from dataclasses import dataclass
from enum import StrEnum

from app.db.models.exchange_account import ExchangeName


class RateLimitScope(StrEnum):
    IP = "IP"
    ACCOUNT = "ACCOUNT"
    USER_ID = "USER_ID"
    CONNECTION = "CONNECTION"
    DYNAMIC = "DYNAMIC"


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    scope: RateLimitScope
    limit: int | None
    interval_seconds: int | None
    applies_to: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class ExchangeRateLimitConfig:
    exchange_name: ExchangeName
    retry_after_header: str | None
    usage_headers: tuple[str, ...]
    rules: tuple[RateLimitRule, ...]
    notes: str = ""

    def rule(self, name: str) -> RateLimitRule:
        for item in self.rules:
            if item.name == name:
                return item
        raise KeyError(f"rate limit rule not configured: {name}")


EXCHANGE_RATE_LIMITS: dict[ExchangeName, ExchangeRateLimitConfig] = {
    ExchangeName.BINANCE: ExchangeRateLimitConfig(
        exchange_name=ExchangeName.BINANCE,
        retry_after_header="Retry-After",
        usage_headers=(
            "X-MBX-USED-WEIGHT-*",
            "X-MBX-ORDER-COUNT-*",
        ),
        rules=(
            RateLimitRule(
                name="REQUEST_WEIGHT",
                scope=RateLimitScope.IP,
                limit=None,
                interval_seconds=None,
                applies_to=("REST", "WebSocket API"),
                notes="Authoritative values are returned by /api/v3/exchangeInfo rateLimits.",
            ),
            RateLimitRule(
                name="RAW_REQUESTS",
                scope=RateLimitScope.IP,
                limit=300_000,
                interval_seconds=300,
                applies_to=("REST",),
                notes="Spot Testnet changelog lists 300,000 raw requests per 5 minutes.",
            ),
            RateLimitRule(
                name="ORDERS",
                scope=RateLimitScope.ACCOUNT,
                limit=None,
                interval_seconds=None,
                applies_to=("REST", "WebSocket API"),
                notes="Order count limits are account-scoped and must use order-count headers.",
            ),
        ),
        notes="Do not run near the limits; back off on 429 or 418 responses.",
    ),
    ExchangeName.BYBIT: ExchangeRateLimitConfig(
        exchange_name=ExchangeName.BYBIT,
        retry_after_header=None,
        usage_headers=(
            "X-Bapi-Limit",
            "X-Bapi-Limit-Status",
            "X-Bapi-Limit-Reset-Timestamp",
        ),
        rules=(
            RateLimitRule(
                name="HTTP_IP",
                scope=RateLimitScope.IP,
                limit=600,
                interval_seconds=5,
                applies_to=("REST",),
                notes="Default HTTP IP cap before 403 access-too-frequent protection.",
            ),
            RateLimitRule(
                name="WEBSOCKET_CONNECTIONS",
                scope=RateLimitScope.IP,
                limit=500,
                interval_seconds=300,
                applies_to=("WebSocket",),
                notes="Connection creation cap per IP.",
            ),
            RateLimitRule(
                name="MARKET_DATA_CONNECTIONS",
                scope=RateLimitScope.IP,
                limit=1_000,
                interval_seconds=None,
                applies_to=("WebSocket market data",),
                notes="Maximum market-data connections per IP.",
            ),
        ),
        notes="Endpoint and account-tier limits must be read from Bybit response headers.",
    ),
    ExchangeName.OKX: ExchangeRateLimitConfig(
        exchange_name=ExchangeName.OKX,
        retry_after_header=None,
        usage_headers=(),
        rules=(
            RateLimitRule(
                name="PUBLIC_REST",
                scope=RateLimitScope.IP,
                limit=None,
                interval_seconds=None,
                applies_to=("REST public",),
                notes="Public unauthenticated REST limits are endpoint-specific and IP-scoped.",
            ),
            RateLimitRule(
                name="PRIVATE_REST",
                scope=RateLimitScope.USER_ID,
                limit=None,
                interval_seconds=None,
                applies_to=("REST private",),
                notes="Private REST limits are endpoint-specific and User ID scoped.",
            ),
            RateLimitRule(
                name="ORDER_MANAGEMENT",
                scope=RateLimitScope.USER_ID,
                limit=None,
                interval_seconds=None,
                applies_to=("REST order", "WebSocket order"),
                notes="Trading API limits are shared across REST and WebSocket channels.",
            ),
        ),
        notes="Back off when OKX returns error code 50011 for rate limit reached.",
    ),
}


def get_exchange_rate_limit_config(exchange_name: ExchangeName) -> ExchangeRateLimitConfig:
    return EXCHANGE_RATE_LIMITS[exchange_name]
