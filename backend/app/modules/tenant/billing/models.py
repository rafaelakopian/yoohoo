"""Tenant DB models for tuition billing: plans, student billing, invoices, payments."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase, TimestampMixin, UUIDMixin


# ─── Enums ───


class BillingFrequency(str, enum.Enum):
    per_lesson = "per_lesson"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    semester = "semester"
    yearly = "yearly"


class StudentBillingStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    cancelled = "cancelled"


class TuitionInvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class TuitionPaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


# ─── Models ───


class TuitionPlan(UUIDMixin, TimestampMixin, TenantBase):
    """Fee structures defined by the school."""

    __tablename__ = "tuition_plans"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    frequency: Mapped[BillingFrequency] = mapped_column(
        Enum(BillingFrequency, name="billing_frequency"), nullable=False
    )
    lesson_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class StudentBilling(UUIDMixin, TimestampMixin, TenantBase):
    """Billing configuration per student."""

    __tablename__ = "student_billing"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tuition_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tuition_plans.id", ondelete="RESTRICT"), nullable=False
    )
    payer_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True, index=True
    )
    payer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[StudentBillingStatus] = mapped_column(
        Enum(StudentBillingStatus, name="student_billing_status"),
        nullable=False,
        default=StudentBillingStatus.active,
    )
    custom_amount_cents: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    discount_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    billing_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    billing_end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class TuitionInvoice(UUIDMixin, TimestampMixin, TenantBase):
    """Tuition invoices sent to parents."""

    __tablename__ = "tuition_invoices"
    __table_args__ = (
        UniqueConstraint(
            "student_billing_id",
            "period_start",
            "period_end",
            name="uq_invoice_billing_period",
        ),
    )

    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    student_billing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_billing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    central_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)

    # Denormalized recipient info (immutable on invoice)
    payer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Period
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Amounts
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    status: Mapped[TuitionInvoiceStatus] = mapped_column(
        Enum(TuitionInvoiceStatus, name="tuition_invoice_status"),
        nullable=False,
        default=TuitionInvoiceStatus.draft,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_items: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checkout_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class TuitionPayment(UUIDMixin, TimestampMixin, TenantBase):
    """Payment records for tuition invoices."""

    __tablename__ = "tuition_payments"

    tuition_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tuition_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    central_payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[TuitionPaymentStatus] = mapped_column(
        Enum(TuitionPaymentStatus, name="tuition_payment_status"),
        nullable=False,
        default=TuitionPaymentStatus.pending,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
