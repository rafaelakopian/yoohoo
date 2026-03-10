"""Drop unused backup_codes_hash column from users table.

Revision ID: 016
Revises: 015
"""

from alembic import op


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "backup_codes_hash")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("users", sa.Column("backup_codes_hash", sa.Text(), nullable=True))
