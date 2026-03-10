"""Make invitation tenant_id nullable for platform-level invitations.

Platform invitations (invitation_type='platform') have no tenant —
tenant_id is NULL. This enables reusing the existing invitation
infrastructure for inviting platform staff.

Revision ID: 021
Revises: 020
Create Date: 2026-03-08
"""

from alembic import op

# revision identifiers
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("invitations", "tenant_id", nullable=True)


def downgrade() -> None:
    # Guard: only set NOT NULL if no NULL records exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM invitations WHERE tenant_id IS NULL
            ) THEN
                ALTER TABLE invitations ALTER COLUMN tenant_id SET NOT NULL;
            ELSE
                RAISE EXCEPTION 'Cannot downgrade: invitations with NULL tenant_id exist. Delete them first.';
            END IF;
        END $$;
    """)
