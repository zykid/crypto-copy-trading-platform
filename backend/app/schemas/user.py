from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.user import UserRole


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=16, max_length=128)


class PasswordChangeResponse(BaseModel):
    changed: bool


class StorageLocationResponse(BaseModel):
    id: str
    label: str
    path: str
    is_current: bool


class MfaStatusResponse(BaseModel):
    enabled: bool
    enrollment_pending: bool


class MfaEnrollmentResponse(BaseModel):
    provisioning_uri: str
    manual_entry_key: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaConfirmResponse(BaseModel):
    enabled: bool
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class MfaDisableResponse(BaseModel):
    disabled: bool
