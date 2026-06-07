from pydantic import BaseModel, ConfigDict, Field

from app.db.models.exchange_account import AccountMode, ExchangeName


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
