from dataclasses import dataclass
from enum import StrEnum

from app.db.models.exchange_account import AccountMode, ExchangeName


class TestnetReadinessStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ExchangeEndpointConfig:
    exchange_name: ExchangeName
    rest_base_url: str
    public_ws_url: str | None
    private_ws_url: str | None
    demo_header_required: bool = False
    notes: str = ""


@dataclass(frozen=True)
class TestnetReadinessResult:
    status: TestnetReadinessStatus
    reasons: tuple[str, ...]


TESTNET_ENDPOINTS: dict[ExchangeName, ExchangeEndpointConfig] = {
    ExchangeName.BINANCE: ExchangeEndpointConfig(
        exchange_name=ExchangeName.BINANCE,
        rest_base_url="https://testnet.binance.vision",
        public_ws_url="wss://stream.testnet.binance.vision/ws",
        private_ws_url=None,
        notes="Binance Spot Testnet data is periodically reset.",
    ),
    ExchangeName.BYBIT: ExchangeEndpointConfig(
        exchange_name=ExchangeName.BYBIT,
        rest_base_url="https://api-testnet.bybit.com",
        public_ws_url="wss://stream-testnet.bybit.com/v5/public/spot",
        private_ws_url="wss://stream-testnet.bybit.com/v5/private",
    ),
    ExchangeName.OKX: ExchangeEndpointConfig(
        exchange_name=ExchangeName.OKX,
        rest_base_url="https://openapi.okx.com",
        public_ws_url="wss://wspap.okx.com:8443/ws/v5/public",
        private_ws_url="wss://wspap.okx.com:8443/ws/v5/private",
        demo_header_required=True,
        notes="OKX Demo Trading REST uses the OKX REST domain with demo trading authentication context.",
    ),
}


def get_testnet_endpoint_config(exchange_name: ExchangeName) -> ExchangeEndpointConfig:
    return TESTNET_ENDPOINTS[exchange_name]


def check_testnet_readiness(
    *,
    exchange_name: ExchangeName,
    account_mode: AccountMode,
    trading_enabled: bool,
    api_key_configured: bool,
) -> TestnetReadinessResult:
    reasons: list[str] = []
    if exchange_name not in TESTNET_ENDPOINTS:
        reasons.append("exchange does not have a configured testnet endpoint")
    if account_mode != AccountMode.TESTNET:
        reasons.append("account mode must be TESTNET")
    if trading_enabled:
        reasons.append("trading must remain disabled for testnet readiness checks")
    if not api_key_configured:
        reasons.append("testnet API key metadata must be configured")

    status = TestnetReadinessStatus.BLOCKED if reasons else TestnetReadinessStatus.READY
    return TestnetReadinessResult(status=status, reasons=tuple(reasons))
