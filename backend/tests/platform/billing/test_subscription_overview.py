"""Tests for subscription overview and pause endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

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
    tenant_name: str | None = None,
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
        name=tenant_name or f"Org {unique}",
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


async def _create_paid_invoice(db, tenant, sub, total_cents=2999):
    """Create a paid platform invoice for a subscription."""
    invoice = Invoice(
        invoice_number=f"INV-PLT-{uuid.uuid4().hex[:6]}",
        invoice_type=InvoiceType.platform,
        tenant_id=tenant.id,
        subscription_id=sub.id,
        recipient_name="Test",
        recipient_email="test@test.nl",
        subtotal_cents=round(total_cents / 1.21),
        tax_cents=total_cents - round(total_cents / 1.21),
        total_cents=total_cents,
        currency="EUR",
        status=InvoiceStatus.paid,
        paid_at=datetime.now(timezone.utc),
        extra_data={"billing_period_year": 2026, "billing_period_month": 1},
    )
    db.add(invoice)
    await db.flush()
    return invoice


# ─── Tests ───


@pytest.mark.asyncio
async def test_list_subscriptions_overview_returns_items(db_session):
    """Overview should return subscription items with enriched data."""
    tenant, owner, plan, sub = await _create_test_data(db_session)

    service = BillingService(db_session)
    result = await service.list_subscriptions_overview()

    assert result["total"] >= 1
    item = next(i for i in result["items"] if i["subscription_id"] == sub.id)
    assert item["tenant_name"] == tenant.name
    assert item["plan_name"] == plan.name
    assert item["plan_price_cents"] == plan.price_cents
    assert item["status"] == "active"


@pytest.mark.asyncio
async def test_list_subscriptions_overview_filter_by_status(db_session):
    """Filtering by status should only return matching subscriptions."""
    await _create_test_data(db_session, sub_status=SubscriptionStatus.active)
    await _create_test_data(db_session, sub_status=SubscriptionStatus.cancelled)

    service = BillingService(db_session)

    active = await service.list_subscriptions_overview(status="active")
    cancelled = await service.list_subscriptions_overview(status="cancelled")

    assert all(i["status"] == "active" for i in active["items"])
    assert all(i["status"] == "cancelled" for i in cancelled["items"])


@pytest.mark.asyncio
async def test_list_subscriptions_overview_invoice_stats(db_session):
    """Invoice stats (total_invoiced_cents, invoice_count) should be populated."""
    tenant, owner, plan, sub = await _create_test_data(db_session)
    await _create_paid_invoice(db_session, tenant, sub, total_cents=2999)
    await _create_paid_invoice(db_session, tenant, sub, total_cents=2999)

    service = BillingService(db_session)
    result = await service.list_subscriptions_overview()

    item = next(i for i in result["items"] if i["subscription_id"] == sub.id)
    assert item["invoice_count"] == 2
    assert item["total_invoiced_cents"] == 5998


@pytest.mark.asyncio
async def test_list_subscriptions_overview_next_invoice_date(db_session):
    """Active subscriptions should have a next_invoice_date, cancelled should not."""
    _, _, _, active_sub = await _create_test_data(
        db_session, sub_status=SubscriptionStatus.active
    )
    _, _, _, cancelled_sub = await _create_test_data(
        db_session, sub_status=SubscriptionStatus.cancelled
    )

    service = BillingService(db_session)
    result = await service.list_subscriptions_overview()

    active_item = next(
        i for i in result["items"] if i["subscription_id"] == active_sub.id
    )
    cancelled_item = next(
        i for i in result["items"] if i["subscription_id"] == cancelled_sub.id
    )

    assert active_item["next_invoice_date"] is not None
    assert cancelled_item["next_invoice_date"] is None


@pytest.mark.asyncio
async def test_list_subscriptions_overview_pagination(db_session):
    """Pagination should limit results and report correct totals."""
    for _ in range(3):
        await _create_test_data(db_session)

    service = BillingService(db_session)
    result = await service.list_subscriptions_overview(page=1, page_size=2)

    assert len(result["items"]) == 2
    assert result["total"] >= 3
    assert result["pages"] >= 2
    assert result["page"] == 1


@pytest.mark.asyncio
async def test_pause_subscription_active(db_session):
    """Pausing an active subscription should set status to paused."""
    tenant, _, _, sub = await _create_test_data(
        db_session, sub_status=SubscriptionStatus.active
    )

    service = BillingService(db_session)
    result = await service.pause_subscription(tenant.id)

    assert result["status"] == "paused"

    # Verify in DB
    db_result = await db_session.execute(
        select(PlatformSubscription).where(PlatformSubscription.id == sub.id)
    )
    db_sub = db_result.scalar_one()
    assert db_sub.status == SubscriptionStatus.paused
    assert db_sub.extra_data.get("paused_at") is not None


@pytest.mark.asyncio
async def test_pause_subscription_rejects_cancelled(db_session):
    """Pausing a cancelled subscription should raise ConflictError."""
    tenant, _, _, _ = await _create_test_data(
        db_session, sub_status=SubscriptionStatus.cancelled
    )

    service = BillingService(db_session)
    with pytest.raises(Exception, match="pauzeren"):
        await service.pause_subscription(tenant.id)


@pytest.mark.asyncio
async def test_paused_subscription_skipped_in_invoice_generation(db_session):
    """Paused subscriptions should not get invoices generated."""
    await _create_test_data(db_session, sub_status=SubscriptionStatus.paused)

    service = BillingService(db_session)
    result = await service.generate_platform_invoices(
        period_year=2026, period_month=10
    )

    assert result["generated"] == 0
