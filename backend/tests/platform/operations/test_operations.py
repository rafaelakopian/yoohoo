"""Tests for Platform Operations module (Fase A)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import TenantMembership
from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def _mock_metrics_counts():
    """Mock TenantMetricsCollector.collect_counts to return test data."""
    mock = AsyncMock(return_value={
        "student_count": 12,
        "teacher_count": 3,
        "active_invoice_count": 2,
    })
    with patch(
        "app.modules.platform.operations.service.TenantMetricsCollector.collect_counts",
        mock,
    ):
        yield mock


@pytest.fixture
def _mock_metrics_full():
    """Mock TenantMetricsCollector.collect_full to return test data."""
    mock = AsyncMock(return_value={
        "student_count": 15,
        "active_student_count": 12,
        "teacher_count": 3,
        "lesson_slot_count": 10,
        "attendance_total_count": 50,
        "attendance_present_count": 42,
        "invoice_stats": {
            "sent_count": 2,
            "paid_count": 5,
            "overdue_count": 1,
            "total_outstanding_cents": 15000,
            "total_paid_cents": 50000,
        },
    })
    with patch(
        "app.modules.platform.operations.service.TenantMetricsCollector.collect_full",
        mock,
    ):
        yield mock


@pytest.fixture
def _mock_metrics_onboarding():
    """Mock TenantMetricsCollector.collect_onboarding to return test data."""
    mock = AsyncMock(return_value={
        "has_students": True,
        "has_schedule": True,
        "has_attendance": False,
        "has_billing_plan": False,
        "last_step_at": None,
    })
    with patch(
        "app.modules.platform.operations.service.TenantMetricsCollector.collect_onboarding",
        mock,
    ):
        yield mock


@pytest.fixture
def _mock_metrics_failure():
    """Mock TenantMetricsCollector.collect_counts to raise an exception."""
    mock = AsyncMock(side_effect=Exception("Connection refused"))
    with patch(
        "app.modules.platform.operations.service.TenantMetricsCollector.collect_counts",
        mock,
    ):
        yield mock


async def _create_test_tenant(
    db: AsyncSession, name: str = "Test School", slug: str = "test-school",
    owner_id: uuid.UUID | None = None, provisioned: bool = True,
) -> Tenant:
    """Create a test tenant with optional settings."""
    tenant = Tenant(
        name=name,
        slug=slug,
        is_active=True,
        is_provisioned=provisioned,
        owner_id=owner_id,
    )
    db.add(tenant)
    await db.flush()

    # Add settings
    settings = TenantSettings(
        tenant_id=tenant.id,
        org_name=name,
        org_email=f"info@{slug}.nl",
    )
    db.add(settings)
    await db.flush()

    return tenant


async def _add_membership(
    db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID,
) -> TenantMembership:
    """Add a user as member to a tenant."""
    membership = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=True,
    )
    db.add(membership)
    await db.flush()
    return membership


# =====================================================================
# A1: Dashboard Tests
# =====================================================================


@pytest.mark.asyncio
async def test_operations_dashboard(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Dashboard returns platform stats and tenant list."""
    # Create a test tenant
    await _create_test_tenant(db_session, provisioned=False)

    resp = await client.get(
        "/api/v1/admin/operations/dashboard", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "total_tenants" in data
    assert "tenants" in data
    assert isinstance(data["tenants"], list)
    assert data["total_tenants"] >= 1


@pytest.mark.asyncio
async def test_operations_dashboard_with_metrics(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    _mock_metrics_counts,
):
    """Dashboard includes product metrics for provisioned tenants."""
    await _create_test_tenant(db_session, slug="metrics-test", provisioned=True)

    # Clear cache to force fresh query
    from app.modules.platform.operations.service import _dashboard_cache
    _dashboard_cache["data"] = None
    _dashboard_cache["cached_at"] = None

    resp = await client.get(
        "/api/v1/admin/operations/dashboard", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Find our provisioned tenant
    provisioned = [t for t in data["tenants"] if t["slug"] == "metrics-test"]
    assert len(provisioned) == 1
    t = provisioned[0]
    assert t["metrics_available"] is True
    assert t["student_count"] == 12
    assert t["teacher_count"] == 3


# =====================================================================
# A2: Tenant 360° Tests
# =====================================================================


@pytest.mark.asyncio
async def test_tenant_360_detail(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    verified_user: dict, _mock_metrics_full,
):
    """Tenant 360 returns full detail with members and metrics."""
    # Get the user ID
    from app.modules.platform.auth.models import User
    from sqlalchemy import select
    user = (await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )).scalar_one()

    tenant = await _create_test_tenant(
        db_session, name="360 School", slug="360-school",
        owner_id=user.id, provisioned=True,
    )
    await _add_membership(db_session, user.id, tenant.id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["name"] == "360 School"
    assert data["slug"] == "360-school"
    assert data["is_provisioned"] is True
    assert data["metrics_available"] is True
    assert data["student_count"] == 15
    assert data["active_student_count"] == 12
    assert data["invoice_stats"]["paid_count"] == 5
    assert len(data["members"]) >= 1
    assert data["settings"]["org_name"] == "360 School"


@pytest.mark.asyncio
async def test_tenant_360_not_found(
    client: AsyncClient, auth_headers: dict,
):
    """404 for unknown tenant."""
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{fake_id}", headers=auth_headers,
    )
    assert resp.status_code == 404


# =====================================================================
# A3: User Lookup Tests
# =====================================================================


@pytest.mark.asyncio
async def test_user_lookup(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
):
    """User lookup finds users by email."""
    email = verified_user["email"]
    # Use at least 3 chars from the email
    query = email[:8]

    resp = await client.get(
        f"/api/v1/admin/operations/users/lookup?q={query}", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(u["email"] == email for u in data)


@pytest.mark.asyncio
async def test_user_lookup_no_results(
    client: AsyncClient, auth_headers: dict,
):
    """User lookup returns empty list for unknown query."""
    resp = await client.get(
        "/api/v1/admin/operations/users/lookup?q=zzz-nobody-exists", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_lookup_min_chars(
    client: AsyncClient, auth_headers: dict,
):
    """User lookup requires minimum 3 characters."""
    resp = await client.get(
        "/api/v1/admin/operations/users/lookup?q=ab", headers=auth_headers,
    )
    assert resp.status_code == 422  # Validation error


# =====================================================================
# A4: Onboarding Tests
# =====================================================================


@pytest.mark.asyncio
async def test_onboarding_overview(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    verified_user: dict, _mock_metrics_onboarding,
):
    """Onboarding overview returns checklist with completion percentage."""
    from app.modules.platform.auth.models import User
    from sqlalchemy import select
    user = (await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )).scalar_one()

    tenant = await _create_test_tenant(
        db_session, name="Onb School", slug="onb-school",
        owner_id=user.id, provisioned=True,
    )
    await _add_membership(db_session, user.id, tenant.id)

    resp = await client.get(
        "/api/v1/admin/operations/onboarding", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # Find our tenant
    onb_items = [i for i in data if i["tenant_slug"] == "onb-school"]
    assert len(onb_items) == 1
    item = onb_items[0]

    assert item["is_provisioned"] is True
    assert item["has_settings"] is True
    assert item["has_students"] is True  # from mock
    assert item["has_attendance"] is False  # from mock
    assert 0 <= item["completion_pct"] <= 100
    assert isinstance(item["missing_steps"], list)


# =====================================================================
# Permission Tests
# =====================================================================


@pytest.mark.asyncio
async def test_operations_requires_permission(
    client: AsyncClient, db_session: AsyncSession,
):
    """Operations endpoints require authentication."""
    resp = await client.get("/api/v1/admin/operations/dashboard")
    assert resp.status_code == 401


# =====================================================================
# Graceful Degradation Tests
# =====================================================================


@pytest.mark.asyncio
async def test_tenant_query_failure_graceful(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    _mock_metrics_failure,
):
    """Dashboard doesn't crash when a tenant DB query fails."""
    await _create_test_tenant(db_session, slug="failing-tenant", provisioned=True)

    # Clear cache
    from app.modules.platform.operations.service import _dashboard_cache
    _dashboard_cache["data"] = None
    _dashboard_cache["cached_at"] = None

    resp = await client.get(
        "/api/v1/admin/operations/dashboard", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # The failing tenant should have metrics_available=False
    failing = [t for t in data["tenants"] if t["slug"] == "failing-tenant"]
    assert len(failing) == 1
    assert failing[0]["metrics_available"] is False
    assert failing[0]["student_count"] == 0
