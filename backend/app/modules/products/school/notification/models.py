import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase, TimestampMixin, UUIDMixin


class NotificationType(str, enum.Enum):
    lesson_reminder = "lesson_reminder"
    absence_alert = "absence_alert"
    schedule_change = "schedule_change"
    attendance_report = "attendance_report"


class NotificationChannel(str, enum.Enum):
    email = "email"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class NotificationPreference(UUIDMixin, TimestampMixin, TenantBase):
    """Per-tenant notification settings per type."""

    __tablename__ = "notification_preferences"

    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"), nullable=False, unique=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    send_to_guardian: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    send_to_teacher: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    send_to_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class NotificationLog(UUIDMixin, TimestampMixin, TenantBase):
    """Record of sent/attempted notifications."""

    __tablename__ = "notification_logs"

    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", create_type=False),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"),
        nullable=False,
        default=NotificationChannel.email,
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class InAppNotification(UUIDMixin, TenantBase):
    """In-app notification for a user."""

    __tablename__ = "in_app_notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", create_type=False),
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
