import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.platform.auth.constants import Role


class PlatformStats(BaseModel):
    total_tenants: int
    active_tenants: int
    provisioned_tenants: int
    total_users: int
    active_users: int


class AdminTenantItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_provisioned: bool
    owner_name: str | None
    member_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminGroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class AdminMembershipInfo(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: Role | None = None
    is_active: bool
    groups: list[AdminGroupSummary] = []

    model_config = {"from_attributes": True}


class AdminTenantDetail(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_provisioned: bool
    owner_name: str | None
    member_count: int
    created_at: datetime
    settings: dict | None
    memberships: list[AdminMembershipInfo]

    model_config = {"from_attributes": True}


class AdminUserItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    email_verified: bool
    membership_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserMembership(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: Role | None = None
    is_active: bool
    groups: list[AdminGroupSummary] = []

    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    email_verified: bool
    totp_enabled: bool = False
    membership_count: int
    created_at: datetime
    last_login_at: datetime | None = None
    memberships: list[AdminUserMembership]

    model_config = {"from_attributes": True}


class PaginatedUserList(BaseModel):
    items: list[AdminUserItem]
    total: int
    skip: int
    limit: int


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, max_length=255)
    is_active: bool | None = None
    email_verified: bool | None = None


class AuditLogItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_email: str | None = None
    action: str
    ip_address: str | None = None
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogItem]
    total: int
    skip: int
    limit: int


class SuperAdminToggle(BaseModel):
    is_superadmin: bool


class AddMembership(BaseModel):
    user_id: uuid.UUID
    role: Role | None = None
    group_id: uuid.UUID | None = None


class TransferOwnership(BaseModel):
    user_id: uuid.UUID | None = None
