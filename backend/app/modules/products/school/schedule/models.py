import enum
import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TenantBase, TimestampMixin, UUIDMixin


class LessonStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    rescheduled = "rescheduled"


class LessonSlot(UUIDMixin, TimestampMixin, TenantBase):
    """Weekly recurring lesson pattern."""

    __tablename__ = "lesson_slots"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )  # 1=Monday, 7=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    teacher_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    instances: Mapped[list["LessonInstance"]] = relationship(
        back_populates="lesson_slot", cascade="all, delete-orphan"
    )


class LessonInstance(UUIDMixin, TimestampMixin, TenantBase):
    """Concrete lesson on a specific date."""

    __tablename__ = "lesson_instances"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "lesson_date", name="uq_lesson_student_date"
        ),
        Index("ix_lesson_instance_date", "lesson_date"),
        Index("ix_lesson_instance_status", "status"),
    )

    lesson_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lesson_slots.id", ondelete="SET NULL"), nullable=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[LessonStatus] = mapped_column(
        Enum(LessonStatus, name="lesson_status"),
        nullable=False,
        default=LessonStatus.scheduled,
    )
    teacher_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    substitute_teacher_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    substitution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rescheduled_to_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rescheduled_to_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    lesson_slot: Mapped[LessonSlot | None] = relationship(back_populates="instances")


class Holiday(UUIDMixin, TimestampMixin, TenantBase):
    """Holiday / vacation period."""

    __tablename__ = "holidays"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
