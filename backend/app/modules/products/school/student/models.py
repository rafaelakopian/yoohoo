import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase, TimestampMixin, UUIDMixin


class Student(UUIDMixin, TimestampMixin, TenantBase):
    __tablename__ = "students"

    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    lesson_day: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lesson_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Parent/guardian info (embedded)
    guardian_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_relationship: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_phone_work: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ParentStudentLink(UUIDMixin, TimestampMixin, TenantBase):
    """Links a parent User (in central DB) to a Student (in tenant DB)."""
    __tablename__ = "parent_student_links"
    __table_args__ = (
        UniqueConstraint("user_id", "student_id", name="uq_parent_student"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)  # User.id from central DB
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="parent"
    )


class TeacherStudentAssignment(UUIDMixin, TimestampMixin, TenantBase):
    """Links a teacher User (in central DB) to a Student (in tenant DB)."""
    __tablename__ = "teacher_student_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "student_id", name="uq_teacher_student"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)  # Teacher User.id from central DB
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
