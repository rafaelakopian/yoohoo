"""Add student billing, address and bank fields.

Revision ID: 008_add_student_billing_fields
Revises: 007_add_import_system
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_add_student_billing_fields"
down_revision: Union[str, None] = "007_add_import_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("student_number", sa.String(50), nullable=True))
    op.add_column("students", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("students", sa.Column("postal_code", sa.String(20), nullable=True))
    op.add_column("students", sa.Column("city", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("invoice_email", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("invoice_cc_email", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("invoice_discount", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("iban", sa.String(34), nullable=True))
    op.add_column("students", sa.Column("bic", sa.String(11), nullable=True))
    op.add_column("students", sa.Column("account_holder_name", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("account_holder_city", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("direct_debit", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("students", "direct_debit")
    op.drop_column("students", "account_holder_city")
    op.drop_column("students", "account_holder_name")
    op.drop_column("students", "bic")
    op.drop_column("students", "iban")
    op.drop_column("students", "invoice_discount")
    op.drop_column("students", "invoice_cc_email")
    op.drop_column("students", "invoice_email")
    op.drop_column("students", "city")
    op.drop_column("students", "postal_code")
    op.drop_column("students", "address")
    op.drop_column("students", "student_number")
