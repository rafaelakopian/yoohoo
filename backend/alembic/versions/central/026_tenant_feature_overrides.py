"""Add tenant_feature_overrides table for per-tenant feature control.

Revision ID: 026
Revises: 025
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_feature_overrides",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("feature_name", sa.String(50), nullable=False),
        sa.Column("trial_days", sa.Integer, nullable=True),
        sa.Column("retention_days", sa.Integer, nullable=True),
        sa.Column("force_on", sa.Boolean, server_default="false", nullable=False),
        sa.Column("force_off", sa.Boolean, server_default="false", nullable=False),
        sa.Column("force_off_reason", sa.String(500), nullable=True),
        sa.Column("force_off_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "forced_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("forced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.UniqueConstraint("tenant_id", "feature_name", name="uq_tenant_feature_override"),
    )


def downgrade() -> None:
    op.drop_table("tenant_feature_overrides")
