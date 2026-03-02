"""Add permission groups, group permissions, user group assignments

Revision ID: 004_add_permission_groups
Revises: 003_add_user_management
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_add_permission_groups"
down_revision: Union[str, None] = "003_add_user_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Permission Groups table ---
    op.create_table(
        "permission_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_group_tenant_slug"),
    )

    # --- Group Permissions table ---
    op.create_table(
        "group_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("permission_codename", sa.String(100), nullable=False),
        sa.UniqueConstraint("group_id", "permission_codename", name="uq_group_permission"),
    )

    # --- User Group Assignments table ---
    op.create_table(
        "user_group_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("permission_groups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )

    # --- Add group_id to invitations ---
    op.add_column(
        "invitations",
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("permission_groups.id", ondelete="SET NULL"), nullable=True),
    )

    # --- Make role nullable in tenant_memberships and invitations ---
    op.alter_column("tenant_memberships", "role", nullable=True)
    op.alter_column("invitations", "role", nullable=True)


def downgrade() -> None:
    # Restore role NOT NULL (requires data cleanup first)
    op.alter_column("invitations", "role", nullable=False)
    op.alter_column("tenant_memberships", "role", nullable=False)

    op.drop_column("invitations", "group_id")
    op.drop_table("user_group_assignments")
    op.drop_table("group_permissions")
    op.drop_table("permission_groups")
