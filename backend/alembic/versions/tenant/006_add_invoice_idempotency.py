"""Add unique constraint for invoice idempotency (billing_id + period)

Revision ID: 006_add_invoice_idempotency
Revises: 005_add_multi_docent
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "006_add_invoice_idempotency"
down_revision: Union[str, None] = "005_add_multi_docent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_invoice_billing_period",
        "tuition_invoices",
        ["student_billing_id", "period_start", "period_end"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invoice_billing_period",
        "tuition_invoices",
        type_="unique",
    )
