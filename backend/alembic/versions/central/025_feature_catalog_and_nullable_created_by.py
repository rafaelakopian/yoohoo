"""Add feature_catalog table + make platform_notifications.created_by_id nullable.

Revision ID: 025
Revises: 024
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- feature_catalog ---
    op.create_table(
        "feature_catalog",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature_name", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("benefits", JSONB, server_default="[]", nullable=True),
        sa.Column("preview_image_url", sa.String(500), nullable=True),
        sa.Column("default_trial_days", sa.Integer, nullable=False, server_default="14"),
        sa.Column("default_retention_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # --- make created_by_id nullable (for system-generated notifications) ---
    op.alter_column(
        "platform_notifications",
        "created_by_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    # Change FK action from CASCADE to SET NULL
    op.drop_constraint(
        "platform_notifications_created_by_id_fkey",
        "platform_notifications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "platform_notifications_created_by_id_fkey",
        "platform_notifications",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Restore CASCADE FK
    op.drop_constraint(
        "platform_notifications_created_by_id_fkey",
        "platform_notifications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "platform_notifications_created_by_id_fkey",
        "platform_notifications",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "platform_notifications",
        "created_by_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_table("feature_catalog")
