"""Add platform_notification_recipients table.

Revision ID: 023
Revises: 022
"""

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_notification_recipients",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "notification_id", sa.Uuid(),
            sa.ForeignKey("platform_notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notification_id", "user_id", name="uq_pnr_notification_user"),
    )
    op.create_index("idx_pnr_user_unread", "platform_notification_recipients", ["user_id", "is_read"])
    op.create_index("idx_pnr_notification", "platform_notification_recipients", ["notification_id"])


def downgrade() -> None:
    op.drop_index("idx_pnr_notification")
    op.drop_index("idx_pnr_user_unread")
    op.drop_table("platform_notification_recipients")
