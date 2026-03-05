"""Operations module schemas — Platform monitoring & insights."""

import uuid
from datetime import datetime

from pydantic import BaseModel


# --- Shared ---


class TenantSettingsSummary(BaseModel):
    """Typed subset of tenant settings — no raw dict leaking."""

    org_name: str | None = None
    org_email: str | None = None
    org_phone: str | None = None
    timezone: str | None = None


class AuditEvent(BaseModel):
    """Sanitized audit event — no raw details/payload for security."""

    action: str
    user_email: str | None = None
    ip_address: str | None = None
    created_at: datetime


class InvoiceStats(BaseModel):
    sent_count: int = 0
    paid_count: int = 0
    overdue_count: int = 0
    total_outstanding_cents: int = 0
    total_paid_cents: int = 0


# --- A1: Tenant Health Dashboard ---


class TenantHealthItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_provisioned: bool
    owner_name: str | None = None
    member_count: int = 0
    created_at: datetime

    # Metrics from tenant DB (only when is_provisioned=True and query succeeds)
    metrics_available: bool = False
    student_count: int = 0
    teacher_count: int = 0  # distinct users in teacher_student_assignments
    active_invoice_count: int = 0  # sent + overdue
    last_activity_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantHealthDashboard(BaseModel):
    total_tenants: int
    active_tenants: int
    provisioned_tenants: int
    total_users: int
    active_users: int
    tenants: list[TenantHealthItem]
    cached_at: datetime | None = None  # UTC, per-process cache timestamp


# --- A2: Tenant 360° Detail ---


class Tenant360Member(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str | None = None
    is_active: bool
    groups: list[str] = []
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class Tenant360Detail(BaseModel):
    # Basis
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_provisioned: bool
    owner_name: str | None = None
    created_at: datetime
    settings: TenantSettingsSummary | None = None

    # Members
    members: list[Tenant360Member] = []

    # Product metrics (from tenant DB)
    metrics_available: bool = False
    student_count: int = 0
    active_student_count: int = 0
    teacher_count: int = 0
    lesson_slot_count: int = 0
    attendance_present_count: int = 0  # last 30 days
    attendance_total_count: int = 0  # last 30 days (rate = present/total)
    invoice_stats: InvoiceStats = InvoiceStats()

    # Activity
    last_activity_at: datetime | None = None
    recent_events: list[AuditEvent] = []

    model_config = {"from_attributes": True}


# --- A3: User Lookup ---


class UserLookupMembership(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: str | None = None
    groups: list[str] = []

    model_config = {"from_attributes": True}


class UserLookupResult(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    email_verified: bool
    totp_enabled: bool
    last_login_at: datetime | None = None
    created_at: datetime
    memberships: list[UserLookupMembership] = []
    active_sessions: int = 0

    model_config = {"from_attributes": True}


# --- A4: Onboarding Tracker ---


class OnboardingItem(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    created_at: datetime

    # Checklist
    is_provisioned: bool
    has_settings: bool  # org_name filled in
    has_members: bool  # member_count >= 2 (owner + at least 1 invited)
    has_students: bool  # at least 1 student in tenant DB
    has_schedule: bool  # at least 1 lesson slot in tenant DB
    has_attendance: bool  # at least 1 attendance record in tenant DB
    has_billing_plan: bool  # at least 1 tuition plan in tenant DB

    # Progress
    completion_pct: int  # 0-100, calculated in service
    missing_steps: list[str] = []  # e.g. ["has_students", "has_schedule"]
    last_step_at: datetime | None = None  # most recent created_at from tenant DB product tables

    model_config = {"from_attributes": True}
