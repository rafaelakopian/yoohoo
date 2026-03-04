"""Add auth enhancements: verification_codes table, User phone fields, RefreshToken session fields.

Revision ID: 014
Revises: 013
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- User table: phone + 2FA method ---
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("users", sa.Column("preferred_2fa_method", sa.String(20), nullable=True))
    op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])
    op.create_index("ix_users_phone_number", "users", ["phone_number"])

    # --- RefreshToken table: session enhancements ---
    op.add_column(
        "refresh_tokens",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "session_type",
            sa.String(20),
            nullable=False,
            server_default="persistent",
        ),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="true"),
    )

    # --- Verification codes table ---
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("sent_to", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_verification_codes_user_purpose",
        "verification_codes",
        ["user_id", "purpose", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("verification_codes")

    op.drop_column("refresh_tokens", "verified")
    op.drop_column("refresh_tokens", "session_type")
    op.drop_column("refresh_tokens", "last_used_at")

    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "preferred_2fa_method")
    op.drop_column("users", "phone_verified")
    op.drop_column("users", "phone_number")
