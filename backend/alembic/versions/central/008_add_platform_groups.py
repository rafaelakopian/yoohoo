"""Make permission_groups.tenant_id nullable for platform-level groups

Revision ID: 008_add_platform_groups
Revises: 007_add_last_login_at
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "008_add_platform_groups"
down_revision: Union[str, None] = "007_add_last_login_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make tenant_id nullable (NULL = platform-level group)
    op.alter_column(
        "permission_groups",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # Add partial unique index for platform groups (tenant_id IS NULL)
    # The existing uq_group_tenant_slug constraint still works for tenant groups
    # because PostgreSQL treats NULL as distinct in unique constraints
    op.create_index(
        "uq_platform_group_slug",
        "permission_groups",
        ["slug"],
        unique=True,
        postgresql_where=text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_platform_group_slug", table_name="permission_groups")
    op.alter_column(
        "permission_groups",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
