"""Tests for resume_subscription service method and API endpoint."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.platform.auth.models import User
from app.modules.platform.billing.models import (
    Invoice,
    InvoiceType,
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.billing.service import BillingService, ResumeMode
from app.modules.platform.billing.subscription_guard import clear_sub_status_cache
from app.modules.platform.tenant_mgmt.models import Tenant
from tests.conftest import TEST_TENANT_UUID


# ─── Helpers ───


async def _ensure_test_tenant(db, tenant_id=TEST_TENANT_UUID):
    """Ensure the test tenant exists in DB."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if result.scalar_one_or_none():
        return
    owner = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@test.nl",
        hashed_password="hashed",
        full_name="Test Owner",
        is_active=True,
        email_verified=True,
    )
    db.add(owner)
    await db.flush()
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug="test",
        is_active=True,
        is_provisioned=True,
        owner_id=owner.id,
    )
    db.add(tenant)
    await db.flush()


async def _create_plan(db, *, price_cents=1999):
    """Create a platform plan."""
    unique = uuid.uuid4().hex[:8]
    features = PlanFeatures(
        billing=FeatureConfig(enabled=True, trial_days=14),
    ).model_dump()
    plan = PlatformPlan(
        name=f"Plan {unique}",
        slug=f"plan-{unique}",
        price_cents=price_cents,
        currency="EUR",
        interval=PlanInterval.monthly,
        is_active=True,
        features=features,
    )
    db.add(plan)
    await db.flush()
    return plan


async def _create_paused_subscription(
    db, plan, *, paused_months_ago=2, tenant_id=TEST_TENANT_UUID
):
    """Create a paused subscription with paused_at in the past."""
    paused_at = datetime.now(timezone.utc) - timedelta(days=paused_months_ago * 30)
    sub = PlatformSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status=SubscriptionStatus.paused,
        extra_data={"paused_at": paused_at.isoformat()},
    )
    db.add(sub)
    await db.flush()
    return sub


@pytest.fixture(autouse=True)
def _clear_sub_cache():
    """Clear subscription status cache between tests."""
    clear_sub_status_cache()
    yield
    clear_sub_status_cache()


# ─── Service Tests ───


@pytest.mark.asyncio
async def test_resume_next_month_no_invoices(db_session):
    """Resume with next_month mode should not generate any invoices."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    await _create_paused_subscription(db_session, plan)

    service = BillingService(db_session)
    result = await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.next_month,
    )

    assert result["status"] == "active"
    assert result["invoices_generated"] == 0


@pytest.mark.asyncio
async def test_resume_backfill_generates_invoices(db_session):
    """Resume with backfill mode should generate invoices for missed months."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session, price_cents=1999)
    await _create_paused_subscription(db_session, plan, paused_months_ago=2)

    service = BillingService(db_session)
    result = await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.backfill,
    )

    assert result["status"] == "active"
    assert result["invoices_generated"] >= 2  # At least 2 months of backfill


@pytest.mark.asyncio
async def test_resume_prorata_generates_one_invoice(db_session):
    """Resume with prorata mode should generate exactly one invoice."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session, price_cents=1999)
    await _create_paused_subscription(db_session, plan, paused_months_ago=1)

    service = BillingService(db_session)
    result = await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.prorata,
    )

    assert result["status"] == "active"
    assert result["invoices_generated"] == 1


@pytest.mark.asyncio
async def test_resume_prorata_amount_is_partial(db_session):
    """Pro-rata invoice should have a lower amount than the full plan price."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session, price_cents=3000)
    await _create_paused_subscription(db_session, plan, paused_months_ago=1)

    service = BillingService(db_session)
    await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.prorata,
    )

    # Check the invoice
    inv_result = await db_session.execute(
        select(Invoice).where(
            Invoice.tenant_id == TEST_TENANT_UUID,
            Invoice.invoice_type == InvoiceType.platform,
        ).order_by(Invoice.created_at.desc())
    )
    invoice = inv_result.scalars().first()
    assert invoice is not None
    # Pro-rata total should be less than or equal to full price
    assert invoice.total_cents <= plan.price_cents
    assert invoice.total_cents > 0


@pytest.mark.asyncio
async def test_resume_fails_on_active_subscription(db_session):
    """Resume should fail if subscription is not paused."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    sub = PlatformSubscription(
        tenant_id=TEST_TENANT_UUID,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
    )
    db_session.add(sub)
    await db_session.flush()

    from app.core.exceptions import ConflictError

    service = BillingService(db_session)
    with pytest.raises(ConflictError):
        await service.resume_subscription(
            tenant_id=TEST_TENANT_UUID,
            resume_mode=ResumeMode.next_month,
        )


@pytest.mark.asyncio
async def test_resume_fails_on_missing_subscription(db_session):
    """Resume should fail if no subscription exists."""
    await _ensure_test_tenant(db_session)

    from app.core.exceptions import NotFoundError

    service = BillingService(db_session)
    random_id = uuid.uuid4()
    with pytest.raises(NotFoundError):
        await service.resume_subscription(
            tenant_id=random_id,
            resume_mode=ResumeMode.next_month,
        )


@pytest.mark.asyncio
async def test_resume_stores_metadata_in_extra_data(db_session):
    """Resume should store resumed_at, resume_mode, and actor in extra_data."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    await _create_paused_subscription(db_session, plan)

    actor_id = uuid.uuid4()
    service = BillingService(db_session)
    await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.backfill,
        actor_id=actor_id,
    )

    # Reload subscription
    result = await db_session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.tenant_id == TEST_TENANT_UUID
        )
    )
    sub = result.scalar_one()
    assert sub.extra_data["resume_mode"] == "backfill"
    assert sub.extra_data["resumed_at"] is not None
    assert sub.extra_data["resumed_by"] == str(actor_id)


@pytest.mark.asyncio
async def test_resume_backfill_is_idempotent(db_session):
    """Backfill should not create duplicate invoices for the same period."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session, price_cents=1999)
    await _create_paused_subscription(db_session, plan, paused_months_ago=1)

    service = BillingService(db_session)

    # First resume
    result1 = await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.backfill,
    )
    first_count = result1["invoices_generated"]
    assert first_count >= 1

    # Re-pause
    sub_result = await db_session.execute(
        select(PlatformSubscription).where(
            PlatformSubscription.tenant_id == TEST_TENANT_UUID
        )
    )
    sub = sub_result.scalar_one()
    sub.status = SubscriptionStatus.paused
    await db_session.flush()

    # Second resume with same mode — should not duplicate
    result2 = await service.resume_subscription(
        tenant_id=TEST_TENANT_UUID,
        resume_mode=ResumeMode.backfill,
    )
    # Second run should generate 0 new invoices (idempotent)
    assert result2["invoices_generated"] == 0


# ─── API Endpoint Test ───


@pytest.mark.asyncio
async def test_resume_endpoint(tenant_client, tenant_auth_headers, db_session):
    """POST /platform/billing/subscriptions/{tenant_id}/resume should work."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan(db_session)
    await _create_paused_subscription(db_session, plan)

    resp = await tenant_client.post(
        f"/api/v1/platform/billing/subscriptions/{TEST_TENANT_UUID}/resume",
        json={"resume_mode": "next_month"},
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["invoices_generated"] == 0


@pytest.mark.asyncio
async def test_resume_endpoint_invalid_mode(tenant_client, tenant_auth_headers, db_session):
    """POST with invalid resume_mode should return 422."""
    # No need to create subscription — schema validation rejects before DB access
    resp = await tenant_client.post(
        f"/api/v1/platform/billing/subscriptions/{TEST_TENANT_UUID}/resume",
        json={"resume_mode": "invalid"},
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 422
