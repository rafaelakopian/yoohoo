"""Add account archive fields for data retention policy.

Revision ID: 018
Revises: 017
"""

from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column(
        "archived_at",
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Gezet bij account deletion. Na data_retention_account_archive_days wordt account geanonimiseerd.",
    ))
    op.add_column("users", sa.Column(
        "anonymized_at",
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Gezet wanneer account volledig geanonimiseerd is door cron job.",
    ))
    op.add_column("users", sa.Column(
        "archived_by",
        sa.String(255),
        nullable=True,
        comment="Wie het account heeft gearchiveerd: user_id (zelf) of admin:{admin_id}",
    ))
    op.create_index("ix_users_archived_at", "users", ["archived_at"])


def downgrade():
    op.drop_index("ix_users_archived_at", "users")
    op.drop_column("users", "archived_by")
    op.drop_column("users", "anonymized_at")
    op.drop_column("users", "archived_at")
