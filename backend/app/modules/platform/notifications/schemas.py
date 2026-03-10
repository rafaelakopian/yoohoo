import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Admin: Create / Update
# ---------------------------------------------------------------------------

class CreatePlatformNotification(BaseModel):
    notification_type: str
    title: str = Field(..., max_length=255)
    message: str
    severity: str = Field(default="info", pattern="^(info|warning|critical)$")
    target_scope: str = Field(default="all", pattern="^(all|specific)$")
    target_tenant_ids: list[uuid.UUID] | None = None
    extra_data: dict | None = None


class UpdatePlatformNotification(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    message: str | None = None
    severity: str | None = Field(default=None, pattern="^(info|warning|critical)$")
    notification_type: str | None = None
    target_scope: str | None = Field(default=None, pattern="^(all|specific)$")
    target_tenant_ids: list[uuid.UUID] | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PlatformNotificationResponse(BaseModel):
    id: uuid.UUID
    notification_type: str
    title: str
    message: str
    severity: str
    created_by_id: uuid.UUID
    is_published: bool
    published_at: datetime | None = None
    target_scope: str
    target_tenant_ids: list[uuid.UUID] | None = None
    extra_data: dict | None = None
    recipient_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformNotificationListItem(BaseModel):
    id: uuid.UUID
    notification_type: str
    title: str
    severity: str
    is_published: bool
    published_at: datetime | None = None
    target_scope: str
    recipient_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedNotifications(BaseModel):
    items: list[PlatformNotificationListItem]
    total: int
    skip: int
    limit: int


# ---------------------------------------------------------------------------
# User inbox
# ---------------------------------------------------------------------------

class InboxItem(BaseModel):
    id: uuid.UUID  # recipient ID
    notification_id: uuid.UUID
    notification_type: str
    title: str
    message: str
    severity: str
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime  # when the notification was published


class PaginatedInbox(BaseModel):
    items: list[InboxItem]
    total: int
    unread_count: int


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

class PreferenceResponse(BaseModel):
    id: uuid.UUID | None = None
    notification_type: str
    type_label: str
    type_description: str
    is_enabled: bool
    email_enabled: bool
    extra_recipient_group_ids: list[uuid.UUID] | None = None

    model_config = {"from_attributes": True}


class UpdatePreference(BaseModel):
    is_enabled: bool | None = None
    email_enabled: bool | None = None
    extra_recipient_group_ids: list[uuid.UUID] | None = None


# ---------------------------------------------------------------------------
# Notification type registry
# ---------------------------------------------------------------------------

class NotificationTypeInfo(BaseModel):
    code: str
    label: str
    description: str
    default_severity: str
