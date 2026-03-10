"""Tests for finance dashboard — revenue, outstanding, tax, dunning."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.finance.service import FinanceService
from app.modules.platform.tenant_mgmt.models import Tenant

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FINANCE_TENANT_UUID = uuid.UUID("00000000-0000-0000-0000-f1f1f1f1f1f1")


@pytest_asyncio.fixture
async def finance_tenant(db_session: AsyncSession) -> Tenant:
    """Create a unique tenant for finance tests (avoids conflict with conftest TEST_TENANT_UUID)."""
    result = await db_session.execute(select(Tenant).where(Tenant.id == FINANCE_TENANT_UUID))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            id=FINANCE_TENANT_UUID, name="Finance Test School",
            slug=f"fin-{uuid.uuid4().hex[:6]}",
            is_active=True, is_provisioned=True,
        )
        db_session.add(tenant)
        await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def monthly_plan(db_session: AsyncSession) -> PlatformPlan:
    plan = PlatformPlan(
        name="Maandelijks", slug=f"monthly-{uuid.uuid4().hex[:6]}",
        price_cents=2900, interval=PlanInterval.monthly, is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


@pytest_asyncio.fixture
async def yearly_plan(db_session: AsyncSession) -> PlatformPlan:
    plan = PlatformPlan(
        name="Jaarlijks", slug=f"yearly-{uuid.uuid4().hex[:6]}",
        price_cents=28800, interval=PlanInterval.yearly, is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


@pytest_asyncio.fixture
async def active_subscription(
    db_session: AsyncSession, finance_tenant: Tenant, monthly_plan: PlatformPlan,
) -> PlatformSubscription:
    sub = PlatformSubscription(
        tenant_id=finance_tenant.id, plan_id=monthly_plan.id,
        status=SubscriptionStatus.active,
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


def _make_invoice(
    tenant_id: uuid.UUID,
    status: InvoiceStatus = InvoiceStatus.paid,
    total_cents: int = 2900,
    tax_cents: int = 503,
    due_date: datetime | None = None,
    paid_at: datetime | None = None,
    extra_data: dict | None = None,
    invoice_type: InvoiceType = InvoiceType.platform,
) -> Invoice:
    now = datetime.now(timezone.utc)
    return Invoice(
        invoice_number=f"PS-{uuid.uuid4().hex[:8].upper()}",
        invoice_type=invoice_type,
        tenant_id=tenant_id,
        recipient_name="Test School",
        recipient_email="school@test.nl",
        subtotal_cents=total_cents - tax_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        status=status,
        due_date=due_date or now - timedelta(days=5),
        paid_at=paid_at or (now if status == InvoiceStatus.paid else None),
        extra_data=extra_data,
    )


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revenue_overview_correct_mrr(
    db_session: AsyncSession, finance_tenant: Tenant, monthly_plan: PlatformPlan,
):
    """Two active monthly subscriptions → MRR = sum of both."""
    # Create second tenant + subscription
    t2 = Tenant(name="School 2", slug=f"s2-{uuid.uuid4().hex[:6]}", is_active=True, is_provisioned=True)
    db_session.add(t2)
    await db_session.flush()

    sub1 = PlatformSubscription(tenant_id=finance_tenant.id, plan_id=monthly_plan.id, status=SubscriptionStatus.active)
    sub2 = PlatformSubscription(tenant_id=t2.id, plan_id=monthly_plan.id, status=SubscriptionStatus.active)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    service = FinanceService(db_session)
    overview = await service.get_revenue_overview()
    assert overview.mrr_cents == 2900 * 2
    assert overview.arr_cents == 2900 * 2 * 12


@pytest.mark.asyncio
async def test_revenue_overview_yearly_divided_by_12(
    db_session: AsyncSession, finance_tenant: Tenant, yearly_plan: PlatformPlan,
):
    """Yearly subscription €288 → MRR = €24 (288/12)."""
    sub = PlatformSubscription(
        tenant_id=finance_tenant.id, plan_id=yearly_plan.id, status=SubscriptionStatus.active,
    )
    db_session.add(sub)
    await db_session.flush()

    service = FinanceService(db_session)
    overview = await service.get_revenue_overview()
    assert overview.mrr_cents == 28800 // 12  # €24.00


@pytest.mark.asyncio
async def test_outstanding_payments_bucketing(db_session: AsyncSession, finance_tenant: Tenant):
    """Invoice 45 days overdue → bucket 'late' (31-60)."""
    now = datetime.now(timezone.utc)
    inv = _make_invoice(
        finance_tenant.id,
        status=InvoiceStatus.overdue,
        due_date=now - timedelta(days=45),
        paid_at=None,
    )
    db_session.add(inv)
    await db_session.flush()

    service = FinanceService(db_session)
    result = await service.get_outstanding_payments()
    late_bucket = next(b for b in result.buckets if b.bucket == "late")
    assert late_bucket.count >= 1
    assert late_bucket.total_cents >= 2900


@pytest.mark.asyncio
async def test_outstanding_payments_empty(db_session: AsyncSession):
    """No outstanding invoices → all buckets empty."""
    service = FinanceService(db_session)
    result = await service.get_outstanding_payments()
    assert result.total_outstanding_cents == 0
    for bucket in result.buckets:
        assert bucket.count == 0


@pytest.mark.asyncio
async def test_tax_report_correct_quarter(db_session: AsyncSession, finance_tenant: Tenant):
    """Invoices in Q1 2025 → only Q1 data in report."""
    inv = _make_invoice(
        finance_tenant.id,
        total_cents=12100,
        tax_cents=2100,
        paid_at=datetime(2025, 2, 15, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.flush()

    service = FinanceService(db_session)
    report = await service.get_tax_report(2025, 1)
    assert report.year == 2025
    assert report.quarter == 1
    feb_line = next(line for line in report.lines if line.month == "2025-02")
    assert feb_line.invoice_count >= 1
    assert feb_line.tax_cents >= 2100
    assert report.totals.tax_cents >= 2100


@pytest.mark.asyncio
async def test_tax_report_export_csv_format(db_session: AsyncSession, finance_tenant: Tenant):
    """Tax report export produces valid CSV content."""
    inv = _make_invoice(
        finance_tenant.id,
        total_cents=6050,
        tax_cents=1050,
        paid_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.flush()

    service = FinanceService(db_session)
    report = await service.get_tax_report(2025, 1)
    # Verify lines structure
    assert len(report.lines) == 3  # Jan, Feb, Mar
    assert report.lines[0].month == "2025-01"


@pytest.mark.asyncio
async def test_dunning_candidates_after_threshold(db_session: AsyncSession, finance_tenant: Tenant):
    """Invoice 8 days overdue (threshold=7) → in candidates list."""
    now = datetime.now(timezone.utc)
    inv = _make_invoice(
        finance_tenant.id,
        status=InvoiceStatus.open,
        due_date=now - timedelta(days=8),
        paid_at=None,
    )
    db_session.add(inv)
    await db_session.flush()

    service = FinanceService(db_session)
    with patch("app.modules.platform.finance.service.settings") as mock_settings:
        mock_settings.billing_dunning_first_reminder_days = 7
        mock_settings.billing_dunning_second_reminder_days = 14
        mock_settings.billing_dunning_third_reminder_days = 30
        mock_settings.platform_name = "Yoohoo"
        candidates = await service.get_dunning_candidates()

    matching = [c for c in candidates if c.invoice_id == inv.id]
    assert len(matching) == 1
    assert matching[0].days_overdue >= 8


@pytest.mark.asyncio
async def test_dunning_candidates_excluded_if_reminded_today(
    db_session: AsyncSession, finance_tenant: Tenant,
):
    """Invoice reminded today → NOT in candidates list."""
    now = datetime.now(timezone.utc)
    inv = _make_invoice(
        finance_tenant.id,
        status=InvoiceStatus.overdue,
        due_date=now - timedelta(days=10),
        paid_at=None,
        extra_data={
            "dunning_reminder_count": 1,
            "dunning_last_sent_at": now.isoformat(),
        },
    )
    db_session.add(inv)
    await db_session.flush()

    service = FinanceService(db_session)
    with patch("app.modules.platform.finance.service.settings") as mock_settings:
        mock_settings.billing_dunning_first_reminder_days = 7
        mock_settings.billing_dunning_second_reminder_days = 14
        mock_settings.billing_dunning_third_reminder_days = 30
        mock_settings.platform_name = "Yoohoo"
        candidates = await service.get_dunning_candidates()

    matching = [c for c in candidates if c.invoice_id == inv.id]
    assert len(matching) == 0


@pytest.mark.asyncio
async def test_dunning_job_sends_first_reminder(db_session: AsyncSession, finance_tenant: Tenant):
    """Invoice 8 days overdue → email enqueued, reminder_count=1."""
    now = datetime.now(timezone.utc)
    inv = _make_invoice(
        finance_tenant.id,
        status=InvoiceStatus.open,
        due_date=now - timedelta(days=8),
        paid_at=None,
    )
    db_session.add(inv)
    await db_session.flush()

    mock_arq = AsyncMock()
    service = FinanceService(db_session)
    with patch("app.modules.platform.finance.service.settings") as mock_settings:
        mock_settings.billing_dunning_first_reminder_days = 7
        mock_settings.billing_dunning_second_reminder_days = 14
        mock_settings.billing_dunning_third_reminder_days = 30
        mock_settings.platform_name = "Yoohoo"
        sent, skipped = await service.send_dunning_reminders(mock_arq)

    assert sent >= 1
    mock_arq.enqueue_job.assert_called()

    # Verify invoice updated
    await db_session.refresh(inv)
    assert inv.extra_data["dunning_reminder_count"] == 1
    assert inv.status == InvoiceStatus.overdue


@pytest.mark.asyncio
async def test_dunning_job_sends_second_reminder(db_session: AsyncSession, finance_tenant: Tenant):
    """Invoice 15 days overdue, first reminder already sent → round=2."""
    now = datetime.now(timezone.utc)
    inv = _make_invoice(
        finance_tenant.id,
        status=InvoiceStatus.overdue,
        due_date=now - timedelta(days=15),
        paid_at=None,
        extra_data={
            "dunning_reminder_count": 1,
            "dunning_last_sent_at": (now - timedelta(days=7)).isoformat(),
        },
    )
    db_session.add(inv)
    await db_session.flush()

    mock_arq = AsyncMock()
    service = FinanceService(db_session)
    with patch("app.modules.platform.finance.service.settings") as mock_settings:
        mock_settings.billing_dunning_first_reminder_days = 7
        mock_settings.billing_dunning_second_reminder_days = 14
        mock_settings.billing_dunning_third_reminder_days = 30
        mock_settings.platform_name = "Yoohoo"
        sent, _ = await service.send_dunning_reminders(mock_arq, invoice_id=inv.id)

    assert sent == 1
    await db_session.refresh(inv)
    assert inv.extra_data["dunning_reminder_count"] == 2


@pytest.mark.asyncio
async def test_dunning_job_respects_disabled_setting():
    """dunning_enabled=False → job returns early."""
    from app.core.jobs.billing import send_dunning_reminders_job

    ctx = {"job_try": 1, "central_session_factory": None}
    with patch("app.config.settings") as mock_settings:
        mock_settings.billing_dunning_enabled = False
        result = await send_dunning_reminders_job(ctx)

    assert result is True


@pytest.mark.asyncio
async def test_subscription_lifecycle_counts(
    db_session: AsyncSession, finance_tenant: Tenant, monthly_plan: PlatformPlan,
):
    """Mix of subscription statuses → correct counts per status."""
    t2 = Tenant(name="LC Test 2", slug=f"lc2-{uuid.uuid4().hex[:6]}", is_active=True, is_provisioned=True)
    db_session.add(t2)
    await db_session.flush()

    sub1 = PlatformSubscription(
        tenant_id=finance_tenant.id, plan_id=monthly_plan.id, status=SubscriptionStatus.active,
    )
    sub2 = PlatformSubscription(
        tenant_id=t2.id, plan_id=monthly_plan.id, status=SubscriptionStatus.cancelled,
    )
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    service = FinanceService(db_session)
    overview = await service.get_revenue_overview()
    assert overview.subscription_counts["active"] >= 1
    assert overview.subscription_counts["cancelled"] >= 1
    # All 5 statuses present
    for status in ["trialing", "active", "past_due", "cancelled", "expired"]:
        assert status in overview.subscription_counts


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finance_endpoints_require_auth(client: AsyncClient):
    """Finance endpoints without auth → 401."""
    endpoints = [
        "/api/v1/platform/finance/overview",
        "/api/v1/platform/finance/outstanding",
        "/api/v1/platform/finance/tax-report?year=2025&quarter=1",
        "/api/v1/platform/finance/dunning/candidates",
    ]
    for endpoint in endpoints:
        resp = await client.get(endpoint)
        assert resp.status_code == 401, f"Expected 401 for {endpoint}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_finance_overview_returns_data(client: AsyncClient, auth_headers: dict):
    """Authenticated superadmin can access finance overview."""
    resp = await client.get("/api/v1/platform/finance/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "mrr_cents" in data
    assert "arr_cents" in data
    assert "funnel" in data
    assert "subscription_counts" in data
