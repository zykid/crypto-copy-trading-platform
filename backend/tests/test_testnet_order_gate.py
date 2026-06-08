from app.db.models.exchange_account import AccountMode, ExchangeName
from app.services.testnet_order_gate import (
    TestnetOrderGateStatus,
    check_testnet_order_gate,
)


def approved_gate_result():
    return check_testnet_order_gate(
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )


def test_testnet_order_gate_blocks_simulation_accounts() -> None:
    result = check_testnet_order_gate(
        exchange_name=ExchangeName.BINANCE,
        account_mode=AccountMode.SIMULATION,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )

    assert result.status == TestnetOrderGateStatus.BLOCKED
    assert result.approved is False
    assert "account mode must be TESTNET before testnet orders" in result.reasons


def test_testnet_order_gate_blocks_real_accounts_even_when_flags_are_enabled() -> None:
    result = check_testnet_order_gate(
        exchange_name=ExchangeName.BYBIT,
        account_mode=AccountMode.REAL,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )

    assert result.status == TestnetOrderGateStatus.BLOCKED
    assert "account mode must be TESTNET before testnet orders" in result.reasons


def test_testnet_order_gate_requires_all_runtime_safety_flags() -> None:
    result = check_testnet_order_gate(
        exchange_name=ExchangeName.OKX,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=False,
        exchange_account_trading_enabled=False,
        risk_trading_enabled=False,
        api_key_configured=False,
        manual_testnet_order_enable_confirmed=False,
    )

    assert result.status == TestnetOrderGateStatus.BLOCKED
    assert "TESTNET_ADAPTERS_ENABLED must be true before testnet orders" in result.reasons
    assert "exchange account trading_enabled must be true before testnet orders" in result.reasons
    assert "risk settings trading_enabled must be true before testnet orders" in result.reasons
    assert "testnet API key metadata must be configured before testnet orders" in result.reasons
    assert "manual testnet order enable confirmation must be recorded" in result.reasons


def test_testnet_order_gate_blocks_mock_exchange() -> None:
    result = check_testnet_order_gate(
        exchange_name=ExchangeName.MOCK,
        account_mode=AccountMode.TESTNET,
        testnet_adapters_enabled=True,
        exchange_account_trading_enabled=True,
        risk_trading_enabled=True,
        api_key_configured=True,
        manual_testnet_order_enable_confirmed=True,
    )

    assert result.status == TestnetOrderGateStatus.BLOCKED
    assert "exchange does not support testnet order routing" in result.reasons


def test_testnet_order_gate_approves_only_when_every_condition_is_true() -> None:
    result = approved_gate_result()

    assert result.status == TestnetOrderGateStatus.APPROVED
    assert result.approved is True
    assert result.reasons == ()
