import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CentralBase, TimestampMixin, UUIDMixin
from app.modules.platform.auth.constants import Role


class User(UUIDMixin, TimestampMixin, CentralBase):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    verification_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Login tracking
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Email change
    pending_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pending_email_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pending_email_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 2FA / TOTP
    totp_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    backup_codes_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_2fa_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Phone (SMS preparation)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    # Password tracking
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[list["TenantMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    group_assignments: Mapped[list["UserGroupAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class TenantMembership(UUIDMixin, TimestampMixin, CentralBase):
    __tablename__ = "tenant_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Optional[Role]] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=None,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    membership_type: Mapped[str] = mapped_column(
        String(20), default="full", server_default="full", nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")

    # Import Tenant for type hinting
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from app.modules.platform.tenant_mgmt.models import Tenant


class RefreshToken(UUIDMixin, CentralBase):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Session enhancements
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    session_type: Mapped[str] = mapped_column(
        String(20), default="persistent", server_default="persistent", nullable=False
    )
    verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    __table_args__ = (
        Index("ix_refresh_tokens_user_device", "user_id", "device_fingerprint"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Invitation(UUIDMixin, TimestampMixin, CentralBase):
    __tablename__ = "invitations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Optional[Role]] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=True,
    )
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invitation_type: Mapped[str] = mapped_column(
        String(20), default="membership", server_default="membership", nullable=False
    )

    # Relationships
    group: Mapped[Optional["PermissionGroup"]] = relationship()


class PasswordResetToken(UUIDMixin, CentralBase):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(UUIDMixin, CentralBase):
    __tablename__ = "audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # Tenant context (nullable for platform-level actions)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)


# --- Permission & Group System ---


class PermissionGroup(UUIDMixin, TimestampMixin, CentralBase):
    """A group of permissions within a tenant."""

    __tablename__ = "permission_groups"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_group_tenant_slug"),
    )

    # Relationships
    permissions: Mapped[list["GroupPermission"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    user_assignments: Mapped[list["UserGroupAssignment"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupPermission(UUIDMixin, CentralBase):
    """Maps a permission codename to a group."""

    __tablename__ = "group_permissions"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_codename: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("group_id", "permission_codename", name="uq_group_permission"),
    )

    # Relationships
    group: Mapped["PermissionGroup"] = relationship(back_populates="permissions")


class UserGroupAssignment(UUIDMixin, TimestampMixin, CentralBase):
    """Assigns a user to a group within a tenant."""

    __tablename__ = "user_group_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="group_assignments")
    group: Mapped["PermissionGroup"] = relationship(back_populates="user_assignments")


class VerificationCode(UUIDMixin, CentralBase):
    """Channel-agnostic verification codes for 2FA email, recovery, phone verify."""

    __tablename__ = "verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # 'email' | 'sms'
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)  # '2fa_login' | '2fa_recovery' | 'phone_verify'
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # masked email/phone
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_verification_codes_user_purpose", "user_id", "purpose"),
    )
