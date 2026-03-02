"""Add parent_student_links table

Revision ID: 003_add_parent_student_links
Revises: 002_add_schedule_notifications
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_parent_student_links"
down_revision: Union[str, None] = "002_add_schedule_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parent_student_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship_type",
            sa.String(50),
            nullable=False,
            server_default="parent",
        ),
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
        sa.UniqueConstraint("user_id", "student_id", name="uq_parent_student"),
    )
    op.create_index("ix_parent_student_user_id", "parent_student_links", ["user_id"])
    op.create_index(
        "ix_parent_student_student_id", "parent_student_links", ["student_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_parent_student_student_id", table_name="parent_student_links")
    op.drop_index("ix_parent_student_user_id", table_name="parent_student_links")
    op.drop_table("parent_student_links")
