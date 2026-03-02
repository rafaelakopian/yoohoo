"""Pydantic schemas for platform billing: providers, plans, subscriptions, invoices, payments."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Payment Provider ───


class ProviderConfigCreate(BaseModel):
    provider_type: str = Field(..., pattern="^(mollie|stripe)$")
    api_key: str = Field(..., min_length=1, max_length=500)
    api_secret: str | None = None
    webhook_secret: str | None = None
    is_default: bool = False
    supported_methods: list[str] | None = None
    extra_config: dict | None = None


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = Field(None, min_length=1, max_length=500)
    api_secret: str | None = None
    webhook_secret: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    supported_methods: list[str] | None = None
    extra_config: dict | None = None


class ProviderConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider_type: str
    is_active: bool
    is_default: bool
    provider_account_id: str | None
    supported_methods: list[str] | None
    extra_config: dict | None
    has_api_key: bool
    has_api_secret: bool
    has_webhook_secret: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Platform Plans ───


class PlatformPlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: str | None = None
    price_cents: int = Field(..., ge=0)
    currency: str = Field(default="EUR", max_length=3)
    interval: str = Field(..., pattern="^(monthly|yearly)$")
    max_students: int | None = Field(None, ge=0)
    max_teachers: int | None = Field(None, ge=0)
    features: dict | None = None
    is_active: bool = True
    sort_order: int = 0


class PlatformPlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    price_cents: int | None = Field(None, ge=0)
    interval: str | None = Field(None, pattern="^(monthly|yearly)$")
    max_students: int | None = None
    max_teachers: int | None = None
    features: dict | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PlatformPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    price_cents: int
    currency: str
    interval: str
    max_students: int | None
    max_teachers: int | None
    features: dict | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Platform Subscriptions ───


class SubscriptionCreate(BaseModel):
    plan_id: uuid.UUID
    status: str = "trialing"


class SubscriptionUpdate(BaseModel):
    plan_id: uuid.UUID | None = None
    status: str | None = None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    provider_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_end: datetime | None
    cancelled_at: datetime | None
    plan: PlatformPlanResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Invoices ───


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_type: str
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID | None
    recipient_name: str
    recipient_email: str
    recipient_address: str | None
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    status: str
    description: str | None
    line_items: list | None
    due_date: datetime | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    skip: int
    limit: int


# ─── Payments ───


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    tenant_id: uuid.UUID
    provider_type: str
    provider_payment_id: str
    amount_cents: int
    currency: str
    status: str
    payment_method: str | None
    failure_reason: str | None
    refund_amount_cents: int
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    skip: int
    limit: int


class RefundRequest(BaseModel):
    amount_cents: int | None = Field(None, ge=1, description="Partial refund amount. Omit for full refund.")
    description: str | None = None
