import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Registry (from code) ---


class PermissionDefResponse(BaseModel):
    codename: str
    label: str
    description: str


class ModulePermissionsResponse(BaseModel):
    module_name: str
    label: str
    permissions: list[PermissionDefResponse]


class PermissionRegistryResponse(BaseModel):
    modules: list[ModulePermissionsResponse]


# --- Groups ---


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    is_default: bool
    permissions: list[str]
    user_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(None, max_length=1000)
    permissions: list[str] = []


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    permissions: list[str] | None = None


# --- User Assignments ---


class UserAssignment(BaseModel):
    user_id: uuid.UUID


class GroupUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    assigned_at: datetime

    model_config = {"from_attributes": True}


# --- Effective Permissions ---


class EffectivePermissionsResponse(BaseModel):
    permissions: list[str]
    groups: list[GroupSummary]
