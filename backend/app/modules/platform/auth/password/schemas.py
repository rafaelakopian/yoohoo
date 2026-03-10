from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.platform.auth.core.validators import validate_password_strength


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    # secrets.token_urlsafe(32) generates 43-char strings; 20 catches empty/trivial tokens
    token: str = Field(..., min_length=20)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

