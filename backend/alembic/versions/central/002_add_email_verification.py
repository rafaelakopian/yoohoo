"""Add email verification columns to users

Revision ID: 002_add_email_verification
Revises: 001_initial_central
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_add_email_verification"
down_revision: Union[str, None] = "001_initial_central"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_hash", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Mark all existing users as verified so they are not locked out
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "email_verified")
