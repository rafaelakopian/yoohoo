"""Finance dashboard schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantRevenue(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    lifetime_value_cents: int
    mrr_cents: int
    subscription_status: str | None
    since: datetime


class RevenueOverview(BaseModel):
    mrr_cents: int
    arr_cents: int
    growth_percent: float | None
    total_revenue_cents: int
    top_tenants: list[TenantRevenue]
    subscription_counts: dict[str, int]
    funnel: dict[str, int]
    generated_at: datetime


class InvoiceAging(BaseModel):
    bucket: str
    days_range: str
    count: int
    total_cents: int
    tenants: list[str]


class OutstandingPayments(BaseModel):
    total_outstanding_cents: int
    buckets: list[InvoiceAging]
    generated_at: datetime


class TaxReportLine(BaseModel):
    month: str
    invoice_count: int
    subtotal_cents: int
    tax_cents: int
    total_cents: int


class TaxReport(BaseModel):
    year: int
    quarter: int
    lines: list[TaxReportLine]
    totals: TaxReportLine
    generated_at: datetime


class DunningCandidate(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    contact_email: str
    invoice_id: uuid.UUID
    invoice_number: str
    amount_cents: int
    days_overdue: int
    reminder_count: int
    last_reminder_sent_at: datetime | None


class DunningSendResult(BaseModel):
    sent: int
    skipped: int
