import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.platform.auth.core.validators import validate_password_strength, validate_phone_e164


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
    remember_me: bool = False


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
    requires_email_verification: bool = False
    available_2fa_methods: list[str] = []


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
    phone_number: str | None = None
    phone_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class MembershipResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
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
    last_login_at: datetime | None = None
    sms_configured: bool = False


class UpdateProfile(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone_number: str | None = Field(None, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return validate_phone_e164(v)


class DeleteAccount(BaseModel):
    password: str


class RequestEmailChange(BaseModel):
    new_email: EmailStr
    password: str


class ConfirmEmailChange(BaseModel):
    token: str


class VerifyLoginSessionRequest(BaseModel):
    token: str
