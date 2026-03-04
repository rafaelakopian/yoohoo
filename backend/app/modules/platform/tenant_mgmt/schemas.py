import json
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_provisioned: bool
    owner_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantDeleteConfirm(BaseModel):
    password: str


class TenantSettingsUpdate(BaseModel):
    org_name: str | None = Field(None, max_length=255)
    org_address: str | None = Field(None, max_length=500)
    org_phone: str | None = Field(None, max_length=50)
    org_email: str | None = Field(None, max_length=255)
    timezone: str | None = Field(None, max_length=50)
    academic_year_start_month: int | None = Field(None, ge=1, le=12)
    extra_settings: dict | None = None

    @field_validator("extra_settings")
    @classmethod
    def validate_extra_settings_size(cls, v: dict | None) -> dict | None:
        if v is not None:
            serialized = json.dumps(v)
            if len(serialized) > 16_384:  # 16 KB max
                raise ValueError("extra_settings mag maximaal 16 KB zijn")
        return v


class TenantSettingsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    org_name: str | None
    org_address: str | None
    org_phone: str | None
    org_email: str | None
    timezone: str
    academic_year_start_month: int
    extra_settings: dict | None

    model_config = {"from_attributes": True}
