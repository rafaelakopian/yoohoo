"""Operations models — support tooling."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CentralBase


class SupportNote(CentralBase):
    """Internal support note attached to a tenant or user."""

    __tablename__ = "support_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    created_by = relationship(
        "User", foreign_keys=[created_by_id], lazy="joined",
    )

    __table_args__ = (
        CheckConstraint(
            "(tenant_id IS NOT NULL AND user_id IS NULL) OR "
            "(tenant_id IS NULL AND user_id IS NOT NULL)",
            name="ck_support_notes_target",
        ),
        Index("ix_support_notes_tenant_id", "tenant_id"),
        Index("ix_support_notes_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        target = f"tenant={self.tenant_id}" if self.tenant_id else f"user={self.user_id}"
        return f"<SupportNote {self.id} {target}>"
