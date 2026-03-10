"""Extend tenant_feature_trials with reset tracking and warning flags.

Revision ID: 027
Revises: 026
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_feature_trials",
        sa.Column("trial_days_snapshot", sa.Integer, nullable=True),
    )
    op.add_column(
        "tenant_feature_trials",
        sa.Column("reset_count", sa.Integer, server_default="0", nullable=False),
    )
    op.add_column(
        "tenant_feature_trials",
        sa.Column(
            "reset_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tenant_feature_trials",
        sa.Column("last_reset_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_feature_trials",
        sa.Column("warning_60_sent", sa.Boolean, server_default="false", nullable=False),
    )
    op.add_column(
        "tenant_feature_trials",
        sa.Column("warning_90_sent", sa.Boolean, server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tenant_feature_trials", "warning_90_sent")
    op.drop_column("tenant_feature_trials", "warning_60_sent")
    op.drop_column("tenant_feature_trials", "last_reset_at")
    op.drop_column("tenant_feature_trials", "reset_by_user_id")
    op.drop_column("tenant_feature_trials", "reset_count")
    op.drop_column("tenant_feature_trials", "trial_days_snapshot")
