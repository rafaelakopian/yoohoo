"""Add 'paused' value to subscription_status enum.

Revision ID: central_028
Revises: central_027
"""

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'paused'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op
    pass
