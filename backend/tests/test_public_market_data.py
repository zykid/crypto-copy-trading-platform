import pytest

from app.services.public_market_data import (
    PublicMarketDataError,
    _normalize_symbol,
    _parse_binance,
    _parse_bybit,
    _parse_okx,
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
