import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.core.validators import validate_password_strength


class CreateInvitation(BaseModel):
    email: EmailStr
    role: Role | None = None
    group_id: uuid.UUID | None = None
    invitation_type: str = "membership"


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role | None = None
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    tenant_id: uuid.UUID
    invited_by_name: str
    expires_at: datetime
    created_at: datetime
    invitation_type: str = "membership"

    model_config = {"from_attributes": True}


class InviteInfo(BaseModel):
    org_name: str
    role: Role | None = None
    group_name: str | None = None
    email: str
    inviter_name: str
    is_existing_user: bool
    invitation_type: str = "membership"


class AcceptInvitation(BaseModel):
    token: str
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
    tenant_name: str


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
