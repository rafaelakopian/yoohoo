import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.platform.auth.core.validators import validate_password_strength


class CreateInvitation(BaseModel):
    email: EmailStr
    group_id: uuid.UUID | None = None
    invitation_type: str = "membership"


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    tenant_id: uuid.UUID | None = None
    invited_by_name: str
    expires_at: datetime
    created_at: datetime
    invitation_type: str = "membership"

    model_config = {"from_attributes": True}


class InviteInfo(BaseModel):
    org_name: str | None = None
    group_name: str | None = None
    email: str
    inviter_name: str
    # Accepted risk: reveals account existence for the invited email only.
    # Scoped to single email per valid token (192-bit entropy, rate-limited 10/5min, expires 72h).
    is_existing_user: bool
    invitation_type: str = "membership"


class AcceptInvitation(BaseModel):
    # secrets.token_urlsafe(32) generates 43-char strings; 20 catches empty/trivial tokens
    token: str = Field(..., min_length=20)
    password: str | None = Field(None, min_length=8, max_length=128)
    full_name: str | None = Field(None, min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password_strength(v)
        return v


class AcceptInvitationResponse(BaseModel):
    message: str
    is_new_user: bool
    tenant_name: str | None = None


class CreateBulkInvitations(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=50)
    group_id: uuid.UUID | None = None


class BulkInvitationResult(BaseModel):
    email: str
    success: bool
    error: str | None = None
    invitation: InvitationResponse | None = None


class BulkInvitationResponse(BaseModel):
    created: int
    failed: int
    results: list[BulkInvitationResult]


class InvitationWithStatus(InvitationResponse):
    status: str  # "pending", "accepted", "revoked", "expired"
    accepted_at: datetime | None = None
