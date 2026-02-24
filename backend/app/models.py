# backend/app/models.py
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# -------------------------
# Shared / utility schemas
# -------------------------


class Message(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None


# -------------------------
# User models (template-close naming)
# -------------------------


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None
    is_superuser: bool | None = None


class UserUpdateMe(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class User(UserBase):
    id: UUID = Field(default_factory=uuid4)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int
