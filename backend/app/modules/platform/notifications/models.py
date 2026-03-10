import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CentralBase, TimestampMixin, UUIDMixin


class PlatformNotification(UUIDMixin, TimestampMixin, CentralBase):
    """A notification created by a platform admin, targeted at tenant organisations."""

    __tablename__ = "platform_notifications"

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="info")

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Targeting: "all" = all tenants, "specific" = only target_tenant_ids
    target_scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="all")
    target_tenant_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    recipients: Mapped[list["PlatformNotificationRecipient"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan",
    )


class PlatformNotificationRecipient(UUIDMixin, CentralBase):
    """Tracks delivery of a platform notification to a specific user."""

    __tablename__ = "platform_notification_recipients"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_pnr_notification_user"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_notifications.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True,
    )

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    notification: Mapped[PlatformNotification] = relationship(back_populates="recipients")


class PlatformNotificationPreference(UUIDMixin, TimestampMixin, CentralBase):
    """Per-tenant configuration for a platform notification type."""

    __tablename__ = "platform_notification_preferences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "notification_type", name="uq_pnp_tenant_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Additional group IDs (beyond owner + admins) that should receive this type
    extra_recipient_group_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
