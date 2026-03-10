"""Drop legacy role columns and user_role enum type.

The Role enum (super_admin, org_admin, teacher, parent) has been fully
replaced by the dynamic PermissionGroup system. The role column on
tenant_memberships and invitations is nullable and unused — all
authorization flows now use group-based permissions.

Revision ID: 020
Revises: 019
Create Date: 2026-03-07
"""

from alembic import op

# revision identifiers
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop role column from tenant_memberships
    op.drop_column("tenant_memberships", "role")

    # Drop role column from invitations
    op.drop_column("invitations", "role")

    # Drop the PostgreSQL enum type
    op.execute("DROP TYPE IF EXISTS user_role")


def downgrade() -> None:
    # Recreate the enum type
    op.execute("CREATE TYPE user_role AS ENUM ('super_admin', 'org_admin', 'teacher', 'parent')")

    # Re-add role column to tenant_memberships
    op.add_column(
        "tenant_memberships",
        op.Column("role", op.Enum("super_admin", "org_admin", "teacher", "parent", name="user_role", create_type=False), nullable=True),
    )

    # Re-add role column to invitations
    op.add_column(
        "invitations",
        op.Column("role", op.Enum("super_admin", "org_admin", "teacher", "parent", name="user_role", create_type=False), nullable=True),
    )
