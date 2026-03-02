import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CentralBase, TimestampMixin, UUIDMixin


class Tenant(UUIDMixin, TimestampMixin, CentralBase):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_provisioned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    settings: Mapped["TenantSettings | None"] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    memberships: Mapped[list["TenantMembership"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from app.modules.platform.auth.models import TenantMembership


class TenantSettings(UUIDMixin, TimestampMixin, CentralBase):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    school_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    school_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    school_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Amsterdam", nullable=False)
    academic_year_start_month: Mapped[int] = mapped_column(default=8, nullable=False)
    extra_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="settings")
