from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.exchange_account import ExchangeAccount
from app.schemas.trading import TestnetOrderSubmitRequest
from app.services.exchange_accounts import get_api_key_secret_metadata, get_owned_account
from app.services.risk_engine import get_or_create_risk_settings
from app.services.testnet_order_gate import TestnetOrderGateResult, check_testnet_order_gate
from app.services.testnet_order_request import TestnetOrderRequestInput


class TestnetOrderApiBlockedError(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("testnet order API request is blocked by the preflight gate")
        self.reasons = reasons


@dataclass(frozen=True)
class TestnetOrderApiContext:
    account: ExchangeAccount
    order: TestnetOrderRequestInput
    gate_result: TestnetOrderGateResult


def build_testnet_order_api_context(
    db: Session,
    *,
    user_id: str,
    payload: TestnetOrderSubmitRequest,
    testnet_adapters_enabled: bool,
) -> TestnetOrderApiContext:
    account = get_owned_account(
        db,
        user_id=user_id,
        account_id=payload.exchange_account_id,
    )
    if account is None:
        raise ValueError("account not found")

    risk_settings = get_or_create_risk_settings(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    secret_metadata = get_api_key_secret_metadata(
        db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    gate_result = check_testnet_order_gate(
        exchange_name=account.exchange_name,
        account_mode=account.account_mode,
        testnet_adapters_enabled=testnet_adapters_enabled,
        exchange_account_trading_enabled=account.trading_enabled,
        risk_trading_enabled=risk_settings.trading_enabled,
        api_key_configured=secret_metadata is not None,
        manual_testnet_order_enable_confirmed=payload.manual_testnet_order_enable_confirmed,
    )
    if not gate_result.approved:
        raise TestnetOrderApiBlockedError(gate_result.reasons)

    order = TestnetOrderRequestInput(
        exchange_name=account.exchange_name,
        symbol=payload.symbol,
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        price=payload.price,
        client_order_id=payload.client_order_id,
    )
    return TestnetOrderApiContext(account=account, order=order, gate_result=gate_result)
