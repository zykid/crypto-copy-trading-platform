from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.exchange_account import ExchangeName
from app.db.models.trading import OrderExecutionStatus, OrderSide, OrderType, SignalSource


class ManualSignalCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    price: Decimal | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    target_position_quantity: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_quantity_or_target(self) -> "ManualSignalCreate":
        if self.quantity is None and self.target_position_quantity is None:
            raise ValueError("quantity or target_position_quantity is required")
        return self


class TradingSignalResponse(BaseModel):
    id: str
    user_id: str
    source: SignalSource
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal | None
    quantity: Decimal | None
    target_position_quantity: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class PositionDeltaPreview(BaseModel):
    symbol: str
    current_quantity: Decimal
    target_quantity: Decimal
    delta_quantity: Decimal
    side: OrderSide | None


class ExecuteSignalRequest(BaseModel):
    exchange_account_id: str


class TestnetOrderSubmitRequest(BaseModel):
    exchange_account_id: str
    symbol: str = Field(min_length=1, max_length=40)
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Field(gt=0)
    price: Decimal | None = Field(default=None, gt=0)
    client_order_id: str = Field(min_length=1, max_length=80)
    manual_testnet_order_enable_confirmed: bool = False

    @model_validator(mode="after")
    def require_price_for_limit(self) -> "TestnetOrderSubmitRequest":
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("limit orders require price")
        return self


class TestnetOrderSubmitResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    client_order_id: str
    request_method: str
    request_path: str
    exchange_response: dict[str, object]


class TestnetOrderAdmissionCheckResponse(BaseModel):
    name: str
    status: str
    required: bool
    detail: str


class TestnetOrderAdmissionResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    account_mode: str
    overall_status: str
    read_only: bool
    order_submission_authorized: bool
    gate_reasons: list[str]
    checks: list[TestnetOrderAdmissionCheckResponse]


class OrderExecutionResponse(BaseModel):
    execution_id: str
    signal_id: str
    exchange_account_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    status: OrderExecutionStatus
    risk_result: dict[str, object] | None
    exchange_response: dict[str, object] | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)
