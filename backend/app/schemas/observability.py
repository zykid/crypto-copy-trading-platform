from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    exchange_account_id: str | None
    action: str
    severity: str
    payload: dict[str, object]
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SystemEventResponse(BaseModel):
    id: str
    user_id: str | None
    exchange_account_id: str | None
    event_type: str
    severity: str
    payload: dict[str, object]
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
