import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.products.school.notification.models import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)


# --- Preferences ---


class NotificationPreferenceUpdate(BaseModel):
    is_enabled: bool | None = None
    send_to_guardian: bool | None = None
    send_to_teacher: bool | None = None
    send_to_admin: bool | None = None
    extra_config: dict | None = None


class NotificationPreferenceResponse(BaseModel):
    id: uuid.UUID
    notification_type: NotificationType
    is_enabled: bool
    send_to_guardian: bool
    send_to_teacher: bool
    send_to_admin: bool
    extra_config: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferenceListResponse(BaseModel):
    items: list[NotificationPreferenceResponse]


# --- Logs ---


class NotificationLogResponse(BaseModel):
    id: uuid.UUID
    notification_type: NotificationType
    channel: NotificationChannel
    recipient_email: str
    recipient_name: str | None
    subject: str
    status: NotificationStatus
    error_message: str | None
    context_data: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogListResponse(BaseModel):
    items: list[NotificationLogResponse]
    total: int
    page: int
    per_page: int


# --- In-App ---


class InAppNotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    notification_type: NotificationType
    is_read: bool
    context_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InAppNotificationListResponse(BaseModel):
    items: list[InAppNotificationResponse]
    total: int
    page: int
    per_page: int


class InAppUnreadCount(BaseModel):
    count: int
