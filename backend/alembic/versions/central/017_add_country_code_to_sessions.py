"""Add country_code to refresh_tokens for GeoIP tracking.

Revision ID: 017
Revises: 016
"""

from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("country_code", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("refresh_tokens", "country_code")
