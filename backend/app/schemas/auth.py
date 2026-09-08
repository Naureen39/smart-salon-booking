import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    # Deliberately has no `role` field — public signup always creates a client.
    # Any extra "role" sent by a caller is ignored (pydantic's default extra="ignore"),
    # which is what defeats a role-escalation attempt at this endpoint.
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
