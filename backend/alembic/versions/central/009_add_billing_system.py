"""Add billing system: payment providers, plans, subscriptions, invoices, payments

Revision ID: 009_add_billing_system
Revises: 008_add_platform_groups
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ENUM as PG_ENUM

revision: str = "009_add_billing_system"
down_revision: Union[str, None] = "008_add_platform_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums (PG_ENUM with create_type=False + raw SQL creation) ---
    # Create types via raw SQL to avoid SQLAlchemy auto-creation conflicts
    op.execute("CREATE TYPE provider_type AS ENUM ('mollie', 'stripe')")
    op.execute("CREATE TYPE plan_interval AS ENUM ('monthly', 'yearly')")
    op.execute("CREATE TYPE subscription_status AS ENUM ('trialing', 'active', 'past_due', 'cancelled', 'expired')")
    op.execute("CREATE TYPE invoice_type AS ENUM ('platform', 'tuition')")
    op.execute("CREATE TYPE invoice_status AS ENUM ('draft', 'open', 'paid', 'overdue', 'cancelled', 'refunded')")
    op.execute("CREATE TYPE payment_status AS ENUM ('pending', 'processing', 'paid', 'failed', 'cancelled', 'expired', 'refunded', 'partially_refunded')")

    # Reference existing types for column definitions (create_type=False)
    provider_type = PG_ENUM('mollie', 'stripe', name='provider_type', create_type=False)
    plan_interval = PG_ENUM('monthly', 'yearly', name='plan_interval', create_type=False)
    subscription_status = PG_ENUM('trialing', 'active', 'past_due', 'cancelled', 'expired', name='subscription_status', create_type=False)
    invoice_type = PG_ENUM('platform', 'tuition', name='invoice_type', create_type=False)
    invoice_status = PG_ENUM('draft', 'open', 'paid', 'overdue', 'cancelled', 'refunded', name='invoice_status', create_type=False)
    payment_status = PG_ENUM('pending', 'processing', 'paid', 'failed', 'cancelled', 'expired', 'refunded', 'partially_refunded', name='payment_status', create_type=False)

    # --- payment_providers ---
    op.create_table(
        "payment_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("api_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("provider_account_id", sa.String(255), nullable=True),
        sa.Column("supported_methods", JSONB(), nullable=True),
        sa.Column("extra_config", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_type", name="uq_tenant_provider"),
    )
    op.create_index("ix_payment_providers_tenant_id", "payment_providers", ["tenant_id"])

    # --- platform_plans ---
    op.create_table(
        "platform_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("interval", plan_interval, nullable=False),
        sa.Column("max_students", sa.Integer(), nullable=True),
        sa.Column("max_teachers", sa.Integer(), nullable=True),
        sa.Column("features", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- platform_subscriptions ---
    op.create_table(
        "platform_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("platform_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", subscription_status, nullable=False, server_default="trialing"),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_subscription_active"),
    )
    op.create_index("ix_platform_subscriptions_tenant_id", "platform_subscriptions", ["tenant_id"])

    # --- invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(50), unique=True, nullable=False),
        sa.Column("invoice_type", invoice_type, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("platform_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_name", sa.String(255), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("recipient_address", sa.Text(), nullable=True),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("status", invoice_status, nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("line_items", JSONB(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("status", payment_status, nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("refund_amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_metadata", JSONB(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider_payment_id"])

    # --- payment_methods ---
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("provider_payment_method_id", sa.String(255), nullable=False),
        sa.Column("method_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_payment_method_id", name="uq_tenant_payment_method"),
    )
    op.create_index("ix_payment_methods_tenant_id", "payment_methods", ["tenant_id"])
    op.create_index("ix_payment_methods_user_id", "payment_methods", ["user_id"])

    # --- webhook_events ---
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", provider_type, nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type", "provider_event_id", name="uq_webhook_event"),
    )
    op.create_index("ix_webhook_events_provider_event_id", "webhook_events", ["provider_event_id"])
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("payment_methods")
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_table("platform_subscriptions")
    op.drop_table("platform_plans")
    op.drop_table("payment_providers")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.execute("DROP TYPE IF EXISTS invoice_type")
    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS plan_interval")
    op.execute("DROP TYPE IF EXISTS provider_type")
