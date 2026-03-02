"""Initial tenant database schema (students + attendance)

Revision ID: 001_initial_tenant
Revises:
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_tenant"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = ("tenant",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Students table
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("lesson_day", sa.String(20), nullable=True),
        sa.Column("lesson_duration", sa.Integer(), nullable=True),
        sa.Column("lesson_time", sa.String(10), nullable=True),
        sa.Column("level", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("guardian_name", sa.String(255), nullable=True),
        sa.Column("guardian_relationship", sa.String(50), nullable=True),
        sa.Column("guardian_phone", sa.String(50), nullable=True),
        sa.Column("guardian_phone_work", sa.String(50), nullable=True),
        sa.Column("guardian_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Attendance records table
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("present", "absent", "sick", "excused", name="attendance_status"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "lesson_date", name="uq_attendance_student_date"),
    )
    op.create_index("ix_attendance_lesson_date", "attendance_records", ["lesson_date"])


def downgrade() -> None:
    op.drop_index("ix_attendance_lesson_date", table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_table("students")
    op.execute("DROP TYPE IF EXISTS attendance_status")
