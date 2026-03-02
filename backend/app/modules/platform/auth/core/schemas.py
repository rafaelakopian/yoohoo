import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.core.validators import validate_password_strength


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Extended login response that supports 2FA flow."""
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    two_factor_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    message: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class MembershipResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role | None = None
    is_active: bool
    membership_type: str = "full"
    groups: list[GroupSummary] = []
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class UserWithMemberships(UserResponse):
    memberships: list[MembershipResponse] = []
    platform_groups: list[GroupSummary] = []
    platform_permissions: list[str] = []
    totp_enabled: bool = False
    backup_codes_remaining: int = 0
    last_login_at: datetime | None = None


class UpdateProfile(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)


class DeleteAccount(BaseModel):
    password: str


class RequestEmailChange(BaseModel):
    new_email: EmailStr
    password: str


class ConfirmEmailChange(BaseModel):
    token: str
