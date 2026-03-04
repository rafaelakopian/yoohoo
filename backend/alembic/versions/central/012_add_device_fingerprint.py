"""Add device_fingerprint to refresh_tokens.

Revision ID: 012
Revises: 011
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("device_fingerprint", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_refresh_tokens_user_device",
        "refresh_tokens",
        ["user_id", "device_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_device", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "device_fingerprint")
