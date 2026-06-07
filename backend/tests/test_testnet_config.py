from app.db.models.exchange_account import AccountMode, ExchangeName
from app.exchanges.testnet_config import (
    TestnetReadinessStatus,
    check_testnet_readiness,
    get_testnet_endpoint_config,
)


def test_known_testnet_endpoint_configs_are_available() -> None:
    binance = get_testnet_endpoint_config(ExchangeName.BINANCE)
    bybit = get_testnet_endpoint_config(ExchangeName.BYBIT)
    okx = get_testnet_endpoint_config(ExchangeName.OKX)

    assert binance.rest_base_url == "https://testnet.binance.vision"
    assert bybit.rest_base_url == "https://api-testnet.bybit.com"
    assert okx.rest_base_url == "https://openapi.okx.com"
    assert okx.demo_header_required is True


def test_simulation_account_is_blocked_from_testnet_readiness() -> None:
    result = check_testnet_readiness(
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.SIMULATION,
        trading_enabled=False,
        api_key_configured=True,
    )

    assert result.status == TestnetReadinessStatus.BLOCKED
    assert "account mode must be TESTNET" in result.reasons


def test_trading_enabled_account_is_blocked_from_readiness_check() -> None:
    result = check_testnet_readiness(
        exchange_name=ExchangeName.BYBIT,
        account_mode=AccountMode.TESTNET,
        trading_enabled=True,
        api_key_configured=True,
    )

    assert result.status == TestnetReadinessStatus.BLOCKED
    assert "trading must remain disabled for testnet readiness checks" in result.reasons


def test_missing_api_key_is_blocked_from_testnet_readiness() -> None:
    result = check_testnet_readiness(
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.TESTNET,
        trading_enabled=False,
        api_key_configured=False,
    )

    assert result.status == TestnetReadinessStatus.BLOCKED
    assert "testnet API key metadata must be configured" in result.reasons


def test_ready_requires_testnet_mode_disabled_trading_and_api_key_metadata() -> None:
    result = check_testnet_readiness(
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.TESTNET,
        trading_enabled=False,
        api_key_configured=True,
    )

    assert result.status == TestnetReadinessStatus.READY
    assert result.reasons == ()
