from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models.user import UserRole


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
