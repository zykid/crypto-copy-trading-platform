from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InternalNotificationResponse(BaseModel):
    id: str
    user_id: str
    exchange_account_id: str | None
    channel: str
    severity: str
    title: str
    message: str
    payload: dict[str, object]
    is_read: bool
    created_at: datetime | None
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceResponse(BaseModel):
    id: str
    user_id: str
    internal_enabled: bool
    telegram_enabled: bool
    email_enabled: bool
    webhook_enabled: bool
    position_drift_enabled: bool
    risk_rejection_enabled: bool
    order_failure_enabled: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceUpdateRequest(BaseModel):
    internal_enabled: bool | None = None
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None
    webhook_enabled: bool | None = None
    position_drift_enabled: bool | None = None
    risk_rejection_enabled: bool | None = None
    order_failure_enabled: bool | None = None
