from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str
    mfa_code: str | None = Field(default=None, min_length=6, max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ReauthenticationRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class ReauthenticationResponse(BaseModel):
    reauthentication_token: str
    expires_in_seconds: int = 300
