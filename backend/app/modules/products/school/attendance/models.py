import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase, TimestampMixin, UUIDMixin


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    sick = "sick"
    excused = "excused"


class AttendanceRecord(UUIDMixin, TimestampMixin, TenantBase):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("student_id", "lesson_date", name="uq_attendance_student_date"),
        Index("ix_attendance_lesson_date", "lesson_date"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"), nullable=False
    )
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
