from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RiskSettingUpdate(BaseModel):
    trading_enabled: bool | None = None
    max_single_order_notional: Decimal | None = Field(default=None, gt=0)
    max_position_notional: Decimal | None = Field(default=None, gt=0)
    max_leverage: Decimal | None = Field(default=None, gt=0)
    min_order_quantity: Decimal | None = Field(default=None, gt=0)
    max_order_quantity: Decimal | None = Field(default=None, gt=0)
    blocked_symbols: list[str] | None = None


class RiskSettingResponse(BaseModel):
    id: str
    user_id: str
    exchange_account_id: str
    trading_enabled: bool
    max_single_order_notional: Decimal | None
    max_position_notional: Decimal | None
    max_leverage: Decimal | None
    min_order_quantity: Decimal | None
    max_order_quantity: Decimal | None
    blocked_symbols: list[str]

    model_config = ConfigDict(from_attributes=True)
