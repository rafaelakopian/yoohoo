"""Add tenant_feature_trials table for feature gating and trial tracking.

Revision ID: 019
Revises: 018
"""

import sqlalchemy as sa
from alembic import op


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_feature_trials",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_slug", sa.String(50), nullable=False),
        sa.Column("feature_name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("trialing", "converted", "expired", "cancelled", "retention", "purged", name="feature_trial_status"),
            nullable=False,
        ),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_retention_days", sa.Integer, nullable=True),
        sa.Column("warning_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "product_slug", "feature_name", name="uq_tenant_feature_trial"),
    )
    op.create_index("ix_tenant_feature_trials_tenant_id", "tenant_feature_trials", ["tenant_id"])
    op.create_index("ix_tenant_feature_trials_status", "tenant_feature_trials", ["status"])
    op.create_index("ix_tenant_feature_trials_retention_until", "tenant_feature_trials", ["retention_until"])


def downgrade() -> None:
    op.drop_table("tenant_feature_trials")
    op.execute("DROP TYPE IF EXISTS feature_trial_status")
