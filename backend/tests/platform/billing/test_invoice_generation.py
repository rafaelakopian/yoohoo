"""Tests for automatic platform invoice generation."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import settings
from app.modules.platform.auth.models import User
from app.modules.platform.billing.models import (
    Invoice,
    InvoiceStatus,
    InvoiceType,
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.billing.service import BillingService
from app.modules.platform.tenant_mgmt.models import Tenant


# ─── Helpers ───


async def _create_test_data(
    db,
    *,
    sub_status: SubscriptionStatus = SubscriptionStatus.active,
    plan_price: int = 2999,
    plan_interval: PlanInterval = PlanInterval.monthly,
):
    """Create tenant + owner + plan + subscription for testing."""
    unique = uuid.uuid4().hex[:8]

    owner = User(
        email=f"owner-{unique}@test.nl",
        hashed_password="hashed",
        full_name=f"Owner {unique}",
        is_active=True,
        email_verified=True,
    )
    db.add(owner)
    await db.flush()

    tenant = Tenant(
        name=f"Org {unique}",
        slug=f"org-{unique}",
        is_active=True,
        is_provisioned=True,
        owner_id=owner.id,
    )
    db.add(tenant)
    await db.flush()

    plan = PlatformPlan(
        name=f"Plan {unique}",
        slug=f"plan-{unique}",
        price_cents=plan_price,
        currency="EUR",
        interval=plan_interval,
        is_active=True,
    )
    db.add(plan)
    await db.flush()

    sub = PlatformSubscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=sub_status,
    )
    db.add(sub)
    await db.flush()

    return tenant, owner, plan, sub


# ─── Tests ───


@pytest.mark.asyncio
async def test_generate_creates_invoice_for_active_subscription(db_session):
    """Active subscription should produce an open invoice."""
    tenant, owner, plan, sub = await _create_test_data(db_session)

    service = BillingService(db_session)
    result = await service.generate_platform_invoices(
        period_year=2026, period_month=2
    )

    assert result["generated"] == 1
    assert result["skipped"] == 0

    # Verify the invoice
    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.platform,
        )
    )
    invoice = inv_result.scalar_one()

    assert invoice.status == InvoiceStatus.open
    assert invoice.recipient_name == owner.full_name
    assert invoice.recipient_email == owner.email
    assert invoice.subscription_id == sub.id
    assert "PLT" in invoice.invoice_number
    assert invoice.description == f"Abonnement {plan.name} — 02/2026"


@pytest.mark.asyncio
async def test_generate_idempotent_skips_existing(db_session):
    """Second run for same period should skip (idempotent)."""
    await _create_test_data(db_session)

    service = BillingService(db_session)
    result1 = await service.generate_platform_invoices(
        period_year=2026, period_month=3
    )
    assert result1["generated"] == 1

    result2 = await service.generate_platform_invoices(
        period_year=2026, period_month=3
    )
    assert result2["generated"] == 0
    assert result2["skipped"] == 1


@pytest.mark.asyncio
async def test_generate_skips_cancelled_subscription(db_session):
    """Cancelled subscriptions should not get an invoice."""
    await _create_test_data(db_session, sub_status=SubscriptionStatus.cancelled)

    service = BillingService(db_session)
    result = await service.generate_platform_invoices(
        period_year=2026, period_month=4
    )

    assert result["generated"] == 0
    assert result["skipped"] == 0  # Not even counted as skipped — not in query


@pytest.mark.asyncio
async def test_generate_correct_amounts_monthly(db_session):
    """Monthly plan should have correct subtotal + tax + total."""
    tenant, _, plan, _ = await _create_test_data(
        db_session, plan_price=2999
    )

    service = BillingService(db_session)
    await service.generate_platform_invoices(
        period_year=2026, period_month=5
    )

    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.platform,
        )
    )
    invoice = inv_result.scalar_one()

    # price_cents is incl BTW — back-calculate excl BTW
    tax_rate = settings.billing_tax_rate_percent / 100
    expected_total = 2999
    expected_subtotal = round(2999 / (1 + tax_rate))
    expected_tax = expected_total - expected_subtotal

    assert invoice.total_cents == expected_total
    assert invoice.subtotal_cents == expected_subtotal
    assert invoice.tax_cents == expected_tax
    assert invoice.currency == "EUR"


@pytest.mark.asyncio
async def test_generate_correct_amounts_yearly(db_session):
    """Yearly plan price should be divided by 12 for monthly invoice."""
    tenant, _, plan, _ = await _create_test_data(
        db_session, plan_price=35988, plan_interval=PlanInterval.yearly
    )

    service = BillingService(db_session)
    await service.generate_platform_invoices(
        period_year=2026, period_month=6
    )

    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.platform,
        )
    )
    invoice = inv_result.scalar_one()

    # Yearly price / 12 = monthly incl BTW, then back-calculate excl
    monthly_total = 35988 // 12  # 2999 incl BTW
    tax_rate = settings.billing_tax_rate_percent / 100
    expected_subtotal = round(monthly_total / (1 + tax_rate))

    assert invoice.total_cents == monthly_total
    assert invoice.subtotal_cents == expected_subtotal


@pytest.mark.asyncio
async def test_generate_due_date_14_days(db_session):
    """Due date should be 14 days after generation."""
    tenant, _, _, _ = await _create_test_data(db_session)

    service = BillingService(db_session)
    await service.generate_platform_invoices(
        period_year=2026, period_month=7
    )

    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.platform,
        )
    )
    invoice = inv_result.scalar_one()

    now = datetime.now(timezone.utc)
    expected_due = now + timedelta(days=settings.billing_invoice_due_days)
    # Allow 5 second margin for test execution time
    assert abs((invoice.due_date - expected_due).total_seconds()) < 5


@pytest.mark.asyncio
async def test_generate_billing_period_in_extra_data(db_session):
    """Extra data should contain billing_period_year and billing_period_month."""
    tenant, _, _, _ = await _create_test_data(db_session)

    service = BillingService(db_session)
    await service.generate_platform_invoices(
        period_year=2026, period_month=8
    )

    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == tenant.id,
            Invoice.invoice_type == InvoiceType.platform,
        )
    )
    invoice = inv_result.scalar_one()

    assert invoice.extra_data["billing_period_year"] == 2026
    assert invoice.extra_data["billing_period_month"] == 8


@pytest.mark.asyncio
async def test_generate_skips_trialing_subscription(db_session):
    """Trialing subscriptions should NOT get an invoice (free trial)."""
    await _create_test_data(db_session, sub_status=SubscriptionStatus.trialing)

    service = BillingService(db_session)
    result = await service.generate_platform_invoices(
        period_year=2026, period_month=9
    )

    assert result["generated"] == 0
