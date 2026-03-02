"""Add tenant_id, entity_type, entity_id to audit_logs.

Revision ID: 011
Revises: 010
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.add_column("audit_logs", sa.Column("entity_type", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("entity_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_audit_logs_tenant_id",
        "audit_logs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_tenant_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "entity_id")
    op.drop_column("audit_logs", "entity_type")
    op.drop_column("audit_logs", "tenant_id")
