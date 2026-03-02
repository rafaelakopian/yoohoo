"""Add multi-docent support: teacher assignments, teacher columns on schedule/attendance

Revision ID: 005_add_multi_docent
Revises: 004_add_tuition_billing
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_add_multi_docent"
down_revision: Union[str, None] = "004_add_tuition_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- teacher_student_assignments ---
    op.create_table(
        "teacher_student_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "student_id", name="uq_teacher_student"),
    )
    op.create_index("ix_teacher_student_user_id", "teacher_student_assignments", ["user_id"])
    op.create_index("ix_teacher_student_student_id", "teacher_student_assignments", ["student_id"])

    # --- Add teacher_user_id to lesson_slots ---
    op.add_column("lesson_slots", sa.Column("teacher_user_id", sa.Uuid(), nullable=True))
    op.create_index("ix_lesson_slot_teacher", "lesson_slots", ["teacher_user_id"])

    # --- Add teacher columns to lesson_instances ---
    op.add_column("lesson_instances", sa.Column("teacher_user_id", sa.Uuid(), nullable=True))
    op.add_column("lesson_instances", sa.Column("substitute_teacher_user_id", sa.Uuid(), nullable=True))
    op.add_column("lesson_instances", sa.Column("substitution_reason", sa.Text(), nullable=True))
    op.create_index("ix_lesson_instance_teacher", "lesson_instances", ["teacher_user_id"])

    # --- Add recorded_by_user_id to attendance_records ---
    op.add_column("attendance_records", sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance_records", "recorded_by_user_id")

    op.drop_index("ix_lesson_instance_teacher", table_name="lesson_instances")
    op.drop_column("lesson_instances", "substitution_reason")
    op.drop_column("lesson_instances", "substitute_teacher_user_id")
    op.drop_column("lesson_instances", "teacher_user_id")

    op.drop_index("ix_lesson_slot_teacher", table_name="lesson_slots")
    op.drop_column("lesson_slots", "teacher_user_id")

    op.drop_index("ix_teacher_student_student_id", table_name="teacher_student_assignments")
    op.drop_index("ix_teacher_student_user_id", table_name="teacher_student_assignments")
    op.drop_table("teacher_student_assignments")
