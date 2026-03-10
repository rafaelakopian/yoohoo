"""Add import system tables.

Revision ID: 007_add_import_system
Revises: 006_add_invoice_idempotency
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007_add_import_system"
down_revision: Union[str, None] = "006_add_invoice_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="preview"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_mapping", JSONB(), nullable=True),
        sa.Column("duplicate_strategy", sa.String(20), nullable=True),
        sa.Column("imported_by", sa.Uuid(), nullable=False),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_batches_entity_type", "import_batches", ["entity_type"]
    )

    op.create_table(
        "import_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("raw_data", JSONB(), nullable=False),
        sa.Column("mapped_data", JSONB(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("duplicate_of", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("previous_data", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_records_batch_id", "import_records", ["batch_id"]
    )


def downgrade() -> None:
    op.drop_table("import_records")
    op.drop_table("import_batches")
