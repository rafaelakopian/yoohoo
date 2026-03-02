"""Add tuition billing: plans, student billing, invoices, payments

Revision ID: 004_add_tuition_billing
Revises: 003_add_parent_student_links
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_add_tuition_billing"
down_revision: Union[str, None] = "003_add_parent_student_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums (created automatically by create_table via schema_item_checkfirst) ---
    billing_frequency = sa.Enum(
        "per_lesson", "weekly", "monthly", "quarterly", "semester", "yearly",
        name="billing_frequency", schema=None,
    )
    student_billing_status = sa.Enum(
        "active", "paused", "cancelled",
        name="student_billing_status", schema=None,
    )
    tuition_invoice_status = sa.Enum(
        "draft", "sent", "paid", "overdue", "cancelled",
        name="tuition_invoice_status", schema=None,
    )
    tuition_payment_status = sa.Enum(
        "pending", "paid", "failed", "refunded",
        name="tuition_payment_status", schema=None,
    )

    # --- tuition_plans ---
    op.create_table(
        "tuition_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("frequency", billing_frequency, nullable=False),
        sa.Column("lesson_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("extra_config", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- student_billing ---
    op.create_table(
        "student_billing",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tuition_plan_id", sa.Uuid(), sa.ForeignKey("tuition_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payer_user_id", sa.Uuid(), nullable=True),
        sa.Column("payer_name", sa.String(255), nullable=False),
        sa.Column("payer_email", sa.String(255), nullable=False),
        sa.Column("status", student_billing_status, nullable=False, server_default="active"),
        sa.Column("custom_amount_cents", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("billing_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("billing_end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_billing_student_id", "student_billing", ["student_id"])
    op.create_index("ix_student_billing_payer_user_id", "student_billing", ["payer_user_id"])

    # --- tuition_invoices ---
    op.create_table(
        "tuition_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(50), unique=True, nullable=False),
        sa.Column("student_billing_id", sa.Uuid(), sa.ForeignKey("student_billing.id", ondelete="CASCADE"), nullable=False),
        sa.Column("central_invoice_id", sa.Uuid(), nullable=True),
        sa.Column("payer_name", sa.String(255), nullable=False),
        sa.Column("payer_email", sa.String(255), nullable=False),
        sa.Column("student_name", sa.String(255), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("status", tuition_invoice_status, nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("line_items", JSONB(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tuition_invoices_invoice_number", "tuition_invoices", ["invoice_number"])
    op.create_index("ix_tuition_invoices_student_billing_id", "tuition_invoices", ["student_billing_id"])

    # --- tuition_payments ---
    op.create_table(
        "tuition_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tuition_invoice_id", sa.Uuid(), sa.ForeignKey("tuition_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("central_payment_id", sa.Uuid(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("status", tuition_payment_status, nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tuition_payments_tuition_invoice_id", "tuition_payments", ["tuition_invoice_id"])


def downgrade() -> None:
    op.drop_table("tuition_payments")
    op.drop_table("tuition_invoices")
    op.drop_table("student_billing")
    op.drop_table("tuition_plans")

    op.execute("DROP TYPE IF EXISTS tuition_payment_status")
    op.execute("DROP TYPE IF EXISTS tuition_invoice_status")
    op.execute("DROP TYPE IF EXISTS student_billing_status")
    op.execute("DROP TYPE IF EXISTS billing_frequency")
