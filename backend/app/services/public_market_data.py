from dataclasses import dataclass
from typing import Any

from app.db.models.exchange_account import ExchangeName
from app.exchanges.http_client import (
    ExchangeHttpRequestError,
    SignedExchangeHttpClient,
)

SUPPORTED_INTERVALS = {"1m", "5m", "15m", "1h"}
PUBLIC_MARKET_BASE_URLS = {
    ExchangeName.OKX: "https://www.okx.com",
    ExchangeName.BINANCE: "https://api.binance.com",
    ExchangeName.BYBIT: "https://api.bybit.com",
}


class PublicMarketDataError(RuntimeError):
    def __init__(self, message: str, *, failure_type: str = "invalid_response") -> None:
        super().__init__(message)
        self.failure_type = failure_type


@dataclass(frozen=True)
class NormalizedCandle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def get_public_candles(
    *,
    exchange_name: ExchangeName,
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[dict[str, int | float]]:
    if exchange_name not in PUBLIC_MARKET_BASE_URLS:
        raise PublicMarketDataError("public candles are not available for this exchange")
    if interval not in SUPPORTED_INTERVALS:
        raise PublicMarketDataError("unsupported candle interval")
    if not 20 <= limit <= 300:
        raise PublicMarketDataError("candle limit must be between 20 and 300")

    normalized_symbol = _normalize_symbol(symbol)
    client = SignedExchangeHttpClient(
        exchange_name=exchange_name,
        rest_base_url=PUBLIC_MARKET_BASE_URLS[exchange_name],
    )
    try:
        if exchange_name == ExchangeName.OKX:
            payload = client.get_public(
                "/api/v5/market/candles",
                params={
                    "instId": _hyphen_symbol(normalized_symbol),
                    "bar": interval,
                    "limit": str(limit),
                },
            )
            candles = _parse_okx(payload)
        elif exchange_name == ExchangeName.BINANCE:
            payload = client.get_public(
                "/api/v3/klines",
                params={"symbol": normalized_symbol, "interval": interval, "limit": str(limit)},
            )
            candles = _parse_binance(payload)
        else:
            payload = client.get_public(
                "/v5/market/kline",
                params={
                    "category": "spot",
                    "symbol": normalized_symbol,
                    "interval": _bybit_interval(interval),
                    "limit": str(limit),
                },
            )
            candles = _parse_bybit(payload)
    except ExchangeHttpRequestError as exc:
        raise PublicMarketDataError(
            "exchange market-data request failed",
            failure_type=exc.failure_type,
        ) from exc

    if not candles:
        raise PublicMarketDataError("exchange returned no candle data")
    return [candle.as_dict() for candle in candles]


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("-", "").strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 24:
        raise PublicMarketDataError("invalid trading symbol")
    return normalized


def _hyphen_symbol(symbol: str) -> str:
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return f"{symbol[:-len(quote)]}-{quote}"
    raise PublicMarketDataError("unsupported quote currency")


def _bybit_interval(interval: str) -> str:
    return {"1m": "1", "5m": "5", "15m": "15", "1h": "60"}[interval]


def _to_candle(row: list[Any], *, seconds: bool = False) -> NormalizedCandle:
    timestamp = int(row[0]) if seconds else int(row[0]) // 1000
    return NormalizedCandle(
        time=timestamp,
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
    )


def _parse_okx(payload: dict[str, Any]) -> list[NormalizedCandle]:
    if payload.get("code") != "0" or not isinstance(payload.get("data"), list):
        raise PublicMarketDataError("invalid OKX candle response")
    return [
        _to_candle(row)
        for row in reversed(payload["data"])
        if isinstance(row, list) and len(row) >= 6
    ]


def _parse_binance(payload: Any) -> list[NormalizedCandle]:
    if not isinstance(payload, list):
        raise PublicMarketDataError("invalid Binance candle response")
    return [_to_candle(row) for row in payload if isinstance(row, list) and len(row) >= 6]


def _parse_bybit(payload: dict[str, Any]) -> list[NormalizedCandle]:
    result = payload.get("result")
    rows = result.get("list") if isinstance(result, dict) else None
    if payload.get("retCode") != 0 or not isinstance(rows, list):
        raise PublicMarketDataError("invalid Bybit candle response")
    return [_to_candle(row) for row in reversed(rows) if isinstance(row, list) and len(row) >= 6]
