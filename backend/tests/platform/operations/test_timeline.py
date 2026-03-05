"""Tests for Customer Timeline (B3)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import AuditLog, User
from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings


# =====================================================================
# Helpers
# =====================================================================


async def _create_test_tenant(db: AsyncSession, slug: str = "timeline-test") -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(name="Timeline Test", slug=slug, is_active=True, is_provisioned=False)
    db.add(tenant)
    await db.flush()
    settings = TenantSettings(tenant_id=tenant.id, org_name="Timeline Test")
    db.add(settings)
    await db.flush()
    return tenant


async def _seed_events(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    """Seed audit log entries for timeline tests."""
    events = [
        AuditLog(action="user.login", tenant_id=tenant_id, user_id=user_id, ip_address="192.168.1.42"),
        AuditLog(action="student.created", tenant_id=tenant_id, user_id=user_id, details={"name": "Emma de Vries"}),
        AuditLog(action="attendance.bulk_created", tenant_id=tenant_id, user_id=user_id, details={"count": 8}),
        AuditLog(action="user.2fa_enabled", tenant_id=tenant_id, user_id=user_id),
        AuditLog(action="billing.invoice_sent", tenant_id=tenant_id, user_id=user_id),
        AuditLog(action="tenant.settings_updated", tenant_id=tenant_id, user_id=user_id),
    ]
    db.add_all(events)
    await db.flush()


async def _get_user_id(db: AsyncSession, email: str) -> uuid.UUID:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    return user.id


# =====================================================================
# Timeline Endpoint
# =====================================================================


@pytest.mark.asyncio
async def test_timeline_basic(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "total_count" in data
    assert "has_more" in data
    assert data["total_count"] == 6
    assert len(data["events"]) == 6


@pytest.mark.asyncio
async def test_timeline_category_filter(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline?category=login",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    for ev in data["events"]:
        assert ev["category"] == "login"


@pytest.mark.asyncio
async def test_timeline_search_filter(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline?search=student",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    for ev in data["events"]:
        assert "student" in ev["action"]


@pytest.mark.asyncio
async def test_timeline_pagination(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline?limit=2&offset=0",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 2
    assert data["has_more"] is True


@pytest.mark.asyncio
async def test_timeline_ip_masking(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    for ev in resp.json()["events"]:
        if ev["ip_address"]:
            assert ev["ip_address"].endswith(".x") or ev["ip_address"].endswith(":x")


@pytest.mark.asyncio
async def test_timeline_categorization(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    valid_categories = {"login", "security", "data", "billing", "system"}
    for ev in resp.json()["events"]:
        assert ev["category"] in valid_categories


@pytest.mark.asyncio
async def test_timeline_details_summary(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession, verified_user: dict,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    user_id = await _get_user_id(db_session, verified_user["email"])
    await _seed_events(db_session, tenant.id, user_id)

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    summaries = {ev["action"]: ev["details_summary"] for ev in resp.json()["events"]}
    assert summaries.get("user.login") == "Ingelogd"
    assert "Emma de Vries" in (summaries.get("student.created") or "")


@pytest.mark.asyncio
async def test_timeline_tenant_not_found(
    client: AsyncClient, auth_headers: dict,
):
    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{uuid.uuid4()}/timeline",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_timeline_invalid_category(
    client: AsyncClient, auth_headers: dict,
    db_session: AsyncSession,
):
    tenant = await _create_test_tenant(db_session, slug=f"tl-{uuid.uuid4().hex[:6]}")
    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/timeline?category=invalid",
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timeline_requires_auth(client: AsyncClient):
    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{uuid.uuid4()}/timeline",
    )
    assert resp.status_code == 401
