"""Add schedule and notification tables

Revision ID: 002_add_schedule_notifications
Revises: 001_initial_tenant
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB

revision: str = "002_add_schedule_notifications"
down_revision: Union[str, None] = "001_initial_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Schedule tables ---

    # Lesson slots (weekly recurring patterns)
    op.create_table(
        "lesson_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create enum types via raw SQL (prevents duplicate creation by create_table)
    op.execute("CREATE TYPE lesson_status AS ENUM ('scheduled', 'completed', 'cancelled', 'rescheduled')")
    op.execute("CREATE TYPE notification_type AS ENUM ('lesson_reminder', 'absence_alert', 'schedule_change', 'attendance_report')")
    op.execute("CREATE TYPE notification_channel AS ENUM ('email')")
    op.execute("CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'failed', 'skipped')")

    # Lesson instances (concrete lessons on a date)
    op.create_table(
        "lesson_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_slot_id", sa.Uuid(), sa.ForeignKey("lesson_slots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "status",
            ENUM("scheduled", "completed", "cancelled", "rescheduled", name="lesson_status", create_type=False),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("rescheduled_to_date", sa.Date(), nullable=True),
        sa.Column("rescheduled_to_time", sa.Time(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "lesson_date", name="uq_lesson_student_date"),
    )
    op.create_index("ix_lesson_instance_date", "lesson_instances", ["lesson_date"])
    op.create_index("ix_lesson_instance_status", "lesson_instances", ["status"])

    # Holidays
    op.create_table(
        "holidays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Notification tables ---

    # Notification preferences
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "notification_type",
            ENUM("lesson_reminder", "absence_alert", "schedule_change", "attendance_report", name="notification_type", create_type=False),
            nullable=False,
            unique=True,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("send_to_guardian", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("send_to_teacher", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("send_to_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extra_config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Notification logs
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "notification_type",
            ENUM("lesson_reminder", "absence_alert", "schedule_change", "attendance_report", name="notification_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "channel",
            ENUM("email", name="notification_channel", create_type=False),
            nullable=False,
            server_default="email",
        ),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column(
            "status",
            ENUM("pending", "sent", "failed", "skipped", name="notification_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("context_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # In-app notifications
    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "notification_type",
            ENUM("lesson_reminder", "absence_alert", "schedule_change", "attendance_report", name="notification_type", create_type=False),
            nullable=False,
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("context_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("in_app_notifications")
    op.drop_table("notification_logs")
    op.drop_table("notification_preferences")
    op.drop_table("holidays")
    op.drop_index("ix_lesson_instance_status", table_name="lesson_instances")
    op.drop_index("ix_lesson_instance_date", table_name="lesson_instances")
    op.drop_table("lesson_instances")
    op.drop_table("lesson_slots")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS lesson_status")
