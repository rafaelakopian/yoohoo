"""Add email change fields to users table

Revision ID: 006_add_email_change_fields
Revises: 005_migrate_roles_to_groups
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_add_email_change_fields"
down_revision: Union[str, None] = "005_migrate_roles_to_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("pending_email_token_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("pending_email_token_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_email_token_expires_at")
    op.drop_column("users", "pending_email_token_hash")
    op.drop_column("users", "pending_email")
