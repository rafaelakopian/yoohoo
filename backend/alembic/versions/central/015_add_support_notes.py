"""Add support_notes table for internal support notes per tenant/user.

Revision ID: 015
Revises: 014
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(tenant_id IS NOT NULL AND user_id IS NULL) OR "
            "(tenant_id IS NULL AND user_id IS NOT NULL)",
            name="ck_support_notes_target",
        ),
    )
    op.create_index("ix_support_notes_tenant_id", "support_notes", ["tenant_id"])
    op.create_index("ix_support_notes_user_id", "support_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_support_notes_user_id", table_name="support_notes")
    op.drop_index("ix_support_notes_tenant_id", table_name="support_notes")
    op.drop_table("support_notes")
