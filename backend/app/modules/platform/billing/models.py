"""Central DB models for platform billing: providers, plans, subscriptions, invoices, payments."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CentralBase, TimestampMixin, UUIDMixin


# ─── Enums ───


class ProviderType(str, enum.Enum):
    mollie = "mollie"
    stripe = "stripe"


class PlanInterval(str, enum.Enum):
    monthly = "monthly"
    yearly = "yearly"


class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    expired = "expired"


class InvoiceType(str, enum.Enum):
    platform = "platform"
    tuition = "tuition"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    paid = "paid"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"
    refunded = "refunded"
    partially_refunded = "partially_refunded"


# ─── Models ───


class PaymentProvider(UUIDMixin, TimestampMixin, CentralBase):
    """Payment provider configuration per tenant. API keys are Fernet-encrypted."""

    __tablename__ = "payment_providers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_type", name="uq_tenant_provider"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Encrypted API credentials (Fernet)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provider-specific account IDs
    provider_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Settings
    supported_methods: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class PlatformPlan(UUIDMixin, TimestampMixin, CentralBase):
    """SaaS subscription plans the platform offers to schools."""

    __tablename__ = "platform_plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    interval: Mapped[PlanInterval] = mapped_column(
        Enum(PlanInterval, name="plan_interval"), nullable=False
    )
    max_students: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_teachers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PlatformSubscription(UUIDMixin, TimestampMixin, CentralBase):
    """A tenant's subscription to a platform plan."""

    __tablename__ = "platform_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_subscription_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=SubscriptionStatus.trialing,
    )
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    plan: Mapped["PlatformPlan"] = relationship()


class Invoice(UUIDMixin, TimestampMixin, CentralBase):
    """Unified invoices for platform and tuition billing."""

    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    invoice_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType, name="invoice_type"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("platform_subscriptions.id", ondelete="SET NULL"), nullable=True
    )

    # Recipient info (denormalized for invoice immutability)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amounts (integer cents)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.draft,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_items: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class Payment(UUIDMixin, TimestampMixin, CentralBase):
    """Payment records linked to invoices."""

    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", create_type=False), nullable=False
    )
    provider_payment_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.pending,
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refund_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")


class PaymentMethod(UUIDMixin, TimestampMixin, CentralBase):
    """Stored payment methods (e.g., SEPA mandates for recurring payments)."""

    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_payment_method_id",
            name="uq_tenant_payment_method",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True, index=True)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", create_type=False), nullable=False
    )
    provider_payment_method_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    method_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class WebhookEvent(UUIDMixin, CentralBase):
    """Idempotent webhook event log. Prevents duplicate processing."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_type", "provider_event_id", name="uq_webhook_event"
        ),
    )

    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", create_type=False), nullable=False
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
