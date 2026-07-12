Exit code: 0
Wall time: 2.4 seconds
Output:
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.trading import OrderSide


class ExchangeAccountCreate(BaseModel):
    exchange_name: ExchangeName
    account_label: str = Field(min_length=1, max_length=120)
    account_mode: AccountMode = AccountMode.SIMULATION
    trading_enabled: bool = False


class ExchangeAccountUpdate(BaseModel):
    account_label: str | None = Field(default=None, min_length=1, max_length=120)
    account_mode: AccountMode | None = None
    trading_enabled: bool | None = None
    is_active: bool | None = None


class ExchangeAccountResponse(BaseModel):
    id: str
    user_id: str
    exchange_name: ExchangeName
    account_label: str
    account_mode: AccountMode
    trading_enabled: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ApiKeySecretUpsert(BaseModel):
    api_key: str = Field(min_length=1, max_length=256)
    api_secret: str = Field(min_length=1, max_length=256)
    passphrase: str | None = Field(default=None, max_length=256)


class ApiKeySecretMetadata(BaseModel):
    exchange_account_id: str
    configured: bool
    has_passphrase: bool
    warning: str = "Disable withdrawal permission on this exchange API key."


class TestnetReadOnlyCheckResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    authenticated: bool
    balance_asset_count: int


class RealReadOnlyCheckResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    authenticated: bool
    balance_asset_count: int


class TestnetOrderReconciliationItemResponse(BaseModel):
    execution_id: str
    status: str
    transitioned: bool
    failure_type: str | None


class TestnetOrderReconciliationResponse(BaseModel):
    exchange_account_id: str
    attempted: int
    transitioned: int
    failed: int
    items: list[TestnetOrderReconciliationItemResponse]


class TestnetUserStreamConsumeRequest(BaseModel):
    max_messages: int = Field(ge=1, le=20)
    acknowledgement: str = Field(min_length=1, max_length=80)


class TestnetUserStreamConsumeResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    status: str
    messages_processed: int
    reconnect_attempts: int


class TestnetOrderWindowApprovalRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: OrderSide
    max_quantity: Decimal = Field(gt=0)
    max_notional: Decimal = Field(gt=0)
    duration_minutes: int = Field(ge=1, le=10)
    acknowledgement: str = Field(min_length=1, max_length=80)


class TestnetOrderWindowApprovalResponse(BaseModel):
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    symbol: str
    side: OrderSide
    max_quantity: Decimal
    max_notional: Decimal
    duration_minutes: int
    order_submission_authorized: bool
    trading_flags_changed: bool


class Phase4ReadinessCheckResponse(BaseModel):
    name: str
    status: str
    required: bool
    detail: str


class Phase4ReadinessReportResponse(BaseModel):
    exchange_account_id: str
    exchange_name: ExchangeName
    account_mode: AccountMode
    overall_status: str
    read_only: bool
    order_submission_authorized: bool
    checks: list[Phase4ReadinessCheckResponse]
    gate_reasons: list[str]


class Phase4SmallFundReviewRequest(BaseModel):
    max_notional: Decimal = Field(gt=0, le=100)
    acknowledgement: str = Field(min_length=1, max_length=120)


class Phase4SmallFundReviewResponse(BaseModel):
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    max_notional: Decimal
    read_only_audit_log_id: str
    order_submission_authorized: bool
    trading_flags_changed: bool


class Phase4SmallFundOrderWindowApprovalRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    side: OrderSide
    max_quantity: Decimal = Field(gt=0)
    limit_price: Decimal = Field(gt=0)
    max_notional: Decimal = Field(gt=0, le=100)
    duration_minutes: int = Field(ge=1, le=10)
    acknowledgement: str = Field(min_length=1, max_length=120)


class Phase4SmallFundOrderWindowApprovalResponse(BaseModel):
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    symbol: str
    side: OrderSide
    max_quantity: Decimal
    limit_price: Decimal
    max_notional: Decimal
    duration_minutes: int
    review_audit_log_id: str
    read_only_audit_log_id: str
    order_submission_authorized: bool
    trading_flags_changed: bool


class Phase4FinalReleaseCheckRequest(BaseModel):
    max_notional: Decimal = Field(gt=0, le=100)
    dedicated_account_confirmed: bool
    account_empty_confirmed: bool
    withdrawals_disabled_confirmed: bool
    delete_api_key_after_test_confirmed: bool
    first_order_stop_review_confirmed: bool
    no_live_order_submission_confirmed: bool
    acknowledgement: str = Field(min_length=1, max_length=120)


class Phase4FinalReleaseCheckResponse(BaseModel):
    audit_log_id: str
    exchange_account_id: str
    exchange_name: ExchangeName
    max_notional: Decimal
    review_audit_log_id: str
    order_window_audit_log_id: str
    order_submission_authorized: bool
    trading_flags_changed: bool

