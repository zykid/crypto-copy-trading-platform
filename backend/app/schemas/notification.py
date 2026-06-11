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
