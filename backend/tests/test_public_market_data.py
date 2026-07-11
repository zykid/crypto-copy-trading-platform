import pytest

from app.db.models.exchange_account import ExchangeName
from app.services import public_market_data
from app.services.public_market_data import (
    PublicMarketDataError,
    _normalize_symbol,
    _parse_binance,
    _parse_bybit,
    _parse_okx,
    get_public_candles_with_fallback,
)


def test_public_candle_parsers_normalize_chronological_data() -> None:
    okx = _parse_okx(
        {
            "code": "0",
            "data": [
                ["2000", "2", "3", "1", "2.5", "8"],
                ["1000", "1", "2", "0.5", "1.5", "5"],
            ],
        }
    )
    binance = _parse_binance([[1000, "1", "2", "0.5", "1.5", "5"]])
    bybit = _parse_bybit(
        {
            "retCode": 0,
            "result": {
                "list": [
                    ["2000", "2", "3", "1", "2.5", "8"],
                    ["1000", "1", "2", "0.5", "1.5", "5"],
                ]
            },
        }
    )

    assert [item.time for item in okx] == [1, 2]
    assert binance[0].close == 1.5
    assert [item.time for item in bybit] == [1, 2]


def test_public_symbol_validation_rejects_path_like_input() -> None:
    assert _normalize_symbol("btc/usdt") == "BTCUSDT"
    with pytest.raises(PublicMarketDataError):
        _normalize_symbol("../BTC-USDT")


def test_public_candles_fall_back_after_transport_failure(monkeypatch) -> None:
    calls: list[ExchangeName] = []

    def fake_loader(*, exchange_name, symbol, interval, limit):
        calls.append(exchange_name)
        if exchange_name == ExchangeName.OKX:
            raise PublicMarketDataError(
                "exchange market-data request failed",
                failure_type="transport_error",
            )
        return [{"time": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}]

    monkeypatch.setattr(public_market_data, "get_public_candles", fake_loader)
    result = get_public_candles_with_fallback(
        exchange_name=ExchangeName.OKX,
        symbol="BTC/USDT",
        interval="1m",
        limit=20,
    )

    assert calls == [ExchangeName.OKX, ExchangeName.BINANCE]
    assert result.source_exchange == ExchangeName.BINANCE
    assert result.fallback_used is True


def test_public_candles_do_not_fall_back_for_invalid_request(monkeypatch) -> None:
    def fake_loader(*, exchange_name, symbol, interval, limit):
        raise PublicMarketDataError("unsupported candle interval")

    monkeypatch.setattr(public_market_data, "get_public_candles", fake_loader)
    with pytest.raises(PublicMarketDataError, match="unsupported candle interval"):
        get_public_candles_with_fallback(
            exchange_name=ExchangeName.OKX,
            symbol="BTC/USDT",
            interval="2m",
            limit=20,
        )
