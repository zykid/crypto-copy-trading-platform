from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class EmergencyStopRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("reason must contain at least 3 non-whitespace characters")
        return normalized


class EmergencyStopActivateRequest(EmergencyStopRequest):
    pass


class EmergencyStopDeactivateRequest(EmergencyStopRequest):
    pass


class EmergencyStopResponse(BaseModel):
    enabled: bool
    reason: str | None
    changed_by_user_id: str | None
    changed_at: datetime
