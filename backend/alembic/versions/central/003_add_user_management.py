"""Add user management system: invitations, password reset, audit, 2FA, sessions

Revision ID: 003_add_user_management
Revises: 002_add_email_verification
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB

revision: str = "003_add_user_management"
down_revision: Union[str, None] = "002_add_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- User columns: 2FA + password tracking ---
    op.add_column(
        "users",
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("backup_codes_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- RefreshToken columns: session metadata ---
    op.add_column(
        "refresh_tokens",
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("user_agent", sa.String(500), nullable=True),
    )

    # --- Invitations table ---
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column(
            "role",
            ENUM("super_admin", "org_admin", "teacher", "parent", name="user_role", create_type=False),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Password Reset Tokens table ---
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Audit Logs table ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("password_reset_tokens")
    op.drop_table("invitations")

    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "ip_address")

    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "backup_codes_hash")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_encrypted")
