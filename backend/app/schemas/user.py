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
