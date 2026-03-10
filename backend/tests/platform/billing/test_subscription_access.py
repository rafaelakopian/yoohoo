"""Tests for subscription access guard and feature_gate status check."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.modules.platform.auth.models import User
from app.modules.platform.billing.feature_gate import FeatureAccess, check_feature_access
from app.modules.platform.billing.models import (
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.billing.subscription_guard import (
    _sub_status_cache,
    clear_sub_status_cache,
)
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


async def _create_plan_with_features(db, *, billing_enabled=True):
    """Create a plan with billing feature enabled/disabled."""
    unique = uuid.uuid4().hex[:8]
    features = PlanFeatures(
        billing=FeatureConfig(enabled=billing_enabled, trial_days=14),
    ).model_dump()
    plan = PlatformPlan(
        name=f"Plan {unique}",
        slug=f"plan-{unique}",
        price_cents=1999,
        currency="EUR",
        interval=PlanInterval.monthly,
        is_active=True,
        features=features,
    )
    db.add(plan)
    await db.flush()
    return plan


async def _create_subscription(db, plan, *, status=SubscriptionStatus.active, tenant_id=TEST_TENANT_UUID):
    """Create a subscription for the test tenant."""
    sub = PlatformSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status=status,
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


# ─── Feature Gate Status Check Tests ───


@pytest.mark.asyncio
async def test_feature_gate_denies_paused_subscription(db_session):
    """Feature gate should return allowed=False for paused subscription with plan feature."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session, billing_enabled=True)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.paused)

    access = await check_feature_access(
        tenant_id=TEST_TENANT_UUID,
        feature_name="billing",
        db=db_session,
    )
    assert access.allowed is False


@pytest.mark.asyncio
async def test_feature_gate_allows_active_subscription(db_session):
    """Feature gate should return allowed=True for active subscription with plan feature."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session, billing_enabled=True)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.active)

    access = await check_feature_access(
        tenant_id=TEST_TENANT_UUID,
        feature_name="billing",
        db=db_session,
    )
    assert access.allowed is True


@pytest.mark.asyncio
async def test_feature_gate_denies_cancelled_subscription(db_session):
    """Feature gate should return allowed=False for cancelled subscription."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session, billing_enabled=True)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.cancelled)

    access = await check_feature_access(
        tenant_id=TEST_TENANT_UUID,
        feature_name="billing",
        db=db_session,
    )
    assert access.allowed is False


@pytest.mark.asyncio
async def test_feature_gate_allows_trialing_subscription(db_session):
    """Feature gate should return allowed=True for trialing subscription."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session, billing_enabled=True)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.trialing)

    access = await check_feature_access(
        tenant_id=TEST_TENANT_UUID,
        feature_name="billing",
        db=db_session,
    )
    assert access.allowed is True


# ─── Subscription Guard API Tests ───


@pytest.mark.asyncio
async def test_paused_tenant_blocked_on_normal_route(
    tenant_client, tenant_auth_headers, db_session
):
    """Paused tenant should get 403 on normal tenant routes (e.g. students)."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.paused)

    resp = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "subscription_paused"
    assert data["detail"]["slug"] == "test"


@pytest.mark.asyncio
async def test_paused_tenant_allowed_on_billing_route(
    tenant_client, tenant_auth_headers, db_session
):
    """Paused tenant should still access billing (whitelisted) routes."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.paused)

    resp = await tenant_client.get(
        "/api/v1/org/test/features",
        headers=tenant_auth_headers,
    )
    # Features endpoint is whitelisted — should not return 403
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_paused_tenant_allowed_on_upgrade_route(
    tenant_client, tenant_auth_headers, db_session
):
    """Paused tenant should access upgrade (whitelisted) route."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.paused)

    resp = await tenant_client.get(
        "/api/v1/org/test/subscription-status",
        headers=tenant_auth_headers,
    )
    # subscription-status is whitelisted
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "paused"


@pytest.mark.asyncio
async def test_cancelled_tenant_blocked_on_normal_route(
    tenant_client, tenant_auth_headers, db_session
):
    """Cancelled tenant should get 403 on normal routes."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.cancelled)

    resp = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "subscription_inactive"


@pytest.mark.asyncio
async def test_active_tenant_has_normal_access(
    tenant_client, tenant_auth_headers, db_session
):
    """Active tenant should access all routes normally."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.active)

    resp = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=tenant_auth_headers,
    )
    # Should not be blocked by subscription guard (may return 200 or other non-403 status)
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_no_subscription_has_normal_access(
    tenant_client, tenant_auth_headers, db_session
):
    """Tenant without subscription should access all routes (free tier)."""
    await _ensure_test_tenant(db_session)
    # No subscription created — should pass through

    resp = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=tenant_auth_headers,
    )
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_subscription_status_endpoint_returns_correct_status(
    tenant_client, tenant_auth_headers, db_session
):
    """GET /org/{slug}/subscription-status should return correct status."""
    await _ensure_test_tenant(db_session)
    plan = await _create_plan_with_features(db_session)
    await _create_subscription(db_session, plan, status=SubscriptionStatus.active)

    resp = await tenant_client.get(
        "/api/v1/org/test/subscription-status",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["plan_name"] is not None


@pytest.mark.asyncio
async def test_subscription_status_endpoint_no_subscription(
    tenant_client, tenant_auth_headers, db_session
):
    """GET /org/{slug}/subscription-status should return 'none' when no subscription."""
    await _ensure_test_tenant(db_session)

    resp = await tenant_client.get(
        "/api/v1/org/test/subscription-status",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "none"
    assert data["plan_name"] is None
