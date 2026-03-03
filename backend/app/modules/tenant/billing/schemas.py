"""Pydantic schemas for tenant tuition billing."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Tuition Plans ───


class TuitionPlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    amount_cents: int = Field(..., ge=0)
    currency: str = Field(default="EUR", max_length=3)
    frequency: str = Field(
        ..., pattern="^(per_lesson|weekly|monthly|quarterly|semester|yearly)$"
    )
    lesson_duration_minutes: int | None = Field(None, ge=1)
    is_active: bool = True
    extra_config: dict | None = None


class TuitionPlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    amount_cents: int | None = Field(None, ge=0)
    frequency: str | None = Field(
        None, pattern="^(per_lesson|weekly|monthly|quarterly|semester|yearly)$"
    )
    lesson_duration_minutes: int | None = None
    is_active: bool | None = None
    extra_config: dict | None = None


class TuitionPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    amount_cents: int
    currency: str
    frequency: str
    lesson_duration_minutes: int | None
    is_active: bool
    extra_config: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Student Billing ───


class StudentBillingCreate(BaseModel):
    student_id: uuid.UUID
    tuition_plan_id: uuid.UUID
    payer_user_id: uuid.UUID | None = None
    payer_name: str = Field(..., min_length=1, max_length=255)
    payer_email: str = Field(..., max_length=255)
    custom_amount_cents: int | None = Field(None, ge=0)
    discount_percent: int | None = Field(None, ge=0, le=100)
    billing_start_date: datetime | None = None
    billing_end_date: datetime | None = None
    notes: str | None = None


class StudentBillingUpdate(BaseModel):
    tuition_plan_id: uuid.UUID | None = None
    payer_user_id: uuid.UUID | None = None
    payer_name: str | None = Field(None, min_length=1, max_length=255)
    payer_email: str | None = Field(None, max_length=255)
    status: str | None = Field(None, pattern="^(active|paused|cancelled)$")
    custom_amount_cents: int | None = None
    discount_percent: int | None = Field(None, ge=0, le=100)
    billing_start_date: datetime | None = None
    billing_end_date: datetime | None = None
    notes: str | None = None


class StudentBillingResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    tuition_plan_id: uuid.UUID
    payer_user_id: uuid.UUID | None
    payer_name: str
    payer_email: str
    status: str
    custom_amount_cents: int | None
    discount_percent: int | None
    billing_start_date: datetime | None
    billing_end_date: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Tuition Invoices ───


class InvoiceGenerateRequest(BaseModel):
    """Request to generate invoices for a billing period."""
    period_start: datetime
    period_end: datetime
    student_billing_ids: list[uuid.UUID] | None = None  # None = all active


class TuitionInvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    student_billing_id: uuid.UUID
    central_invoice_id: uuid.UUID | None
    payer_name: str
    payer_email: str
    student_name: str
    period_start: datetime
    period_end: datetime
    subtotal_cents: int
    discount_cents: int
    total_cents: int
    currency: str
    status: str
    description: str | None
    line_items: list | None
    due_date: datetime | None
    sent_at: datetime | None
    paid_at: datetime | None
    checkout_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TuitionInvoiceListResponse(BaseModel):
    items: list[TuitionInvoiceResponse]
    total: int
    skip: int
    limit: int
