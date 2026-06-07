from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeAccount
from app.db.models.trading import OrderSide, RiskDecision, RiskSetting


@dataclass(frozen=True)
class RiskCheckResult:
    decision: RiskDecision
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"decision": self.decision.value, "reasons": self.reasons}


@dataclass(frozen=True)
class RiskOrderInput:
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal | None


def get_or_create_risk_settings(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
) -> RiskSetting:
    settings = db.scalar(
        select(RiskSetting).where(
            RiskSetting.user_id == user_id,
            RiskSetting.exchange_account_id == exchange_account_id,
        )
    )
    if settings is None:
        settings = RiskSetting(
            user_id=user_id,
            exchange_account_id=exchange_account_id,
            trading_enabled=False,
            blocked_symbols=[],
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_risk_settings(
    db: Session,
    settings: RiskSetting,
    data: dict[str, object],
) -> RiskSetting:
    for key, value in data.items():
        if key == "blocked_symbols" and value is not None:
            value = sorted({str(symbol).upper() for symbol in value})
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


def check_order_risk(
    *,
    account: ExchangeAccount,
    settings: RiskSetting,
    order: RiskOrderInput,
) -> RiskCheckResult:
    reasons: list[str] = []
    if account.account_mode != AccountMode.SIMULATION:
        reasons.append("only SIMULATION mode is enabled in V1")
    if not account.trading_enabled:
        reasons.append("exchange account trading is disabled")
    if not settings.trading_enabled:
        reasons.append("risk settings trading is disabled")
    if order.symbol in settings.blocked_symbols:
        reasons.append("symbol is blocked")
    if settings.min_order_quantity is not None and order.quantity < settings.min_order_quantity:
        reasons.append("quantity is below minimum")
    if settings.max_order_quantity is not None and order.quantity > settings.max_order_quantity:
        reasons.append("quantity is above maximum")
    if settings.max_single_order_notional is not None:
        price = order.price or Decimal("1")
        if order.quantity * price > settings.max_single_order_notional:
            reasons.append("single order notional exceeds limit")
    decision = RiskDecision.REJECTED if reasons else RiskDecision.PASSED
    return RiskCheckResult(decision=decision, reasons=reasons)
