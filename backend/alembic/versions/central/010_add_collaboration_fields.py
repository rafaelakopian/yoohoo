"""Add collaboration fields to tenant_memberships and invitations.

Revision ID: 010
Revises: 009_add_billing_system
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009_add_billing_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_memberships",
        sa.Column("membership_type", sa.String(20), nullable=False, server_default="full"),
    )
    op.add_column(
        "invitations",
        sa.Column("invitation_type", sa.String(20), nullable=False, server_default="membership"),
    )


def downgrade() -> None:
    op.drop_column("invitations", "invitation_type")
    op.drop_column("tenant_memberships", "membership_type")
