from dataclasses import dataclass
from enum import StrEnum

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.exchanges.testnet_config import TESTNET_ENDPOINTS


class TestnetOrderGateStatus(StrEnum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TestnetOrderGateResult:
    status: TestnetOrderGateStatus
    reasons: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return self.status == TestnetOrderGateStatus.APPROVED


def check_testnet_order_gate(
    *,
    exchange_name: ExchangeName,
    account_mode: AccountMode,
    testnet_adapters_enabled: bool,
    exchange_account_trading_enabled: bool,
    risk_trading_enabled: bool,
    api_key_configured: bool,
    manual_testnet_order_enable_confirmed: bool,
) -> TestnetOrderGateResult:
    reasons: list[str] = []
    if exchange_name not in TESTNET_ENDPOINTS:
        reasons.append("exchange does not support testnet order routing")
    if account_mode != AccountMode.TESTNET:
        reasons.append("account mode must be TESTNET before testnet orders")
    if not testnet_adapters_enabled:
        reasons.append("TESTNET_ADAPTERS_ENABLED must be true before testnet orders")
    if not exchange_account_trading_enabled:
        reasons.append("exchange account trading_enabled must be true before testnet orders")
    if not risk_trading_enabled:
        reasons.append("risk settings trading_enabled must be true before testnet orders")
    if not api_key_configured:
        reasons.append("testnet API key metadata must be configured before testnet orders")
    if not manual_testnet_order_enable_confirmed:
        reasons.append("manual testnet order enable confirmation must be recorded")

    status = TestnetOrderGateStatus.BLOCKED if reasons else TestnetOrderGateStatus.APPROVED
    return TestnetOrderGateResult(status=status, reasons=tuple(reasons))
