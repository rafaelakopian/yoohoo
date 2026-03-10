"""Tests for the members listing endpoint (Fase 6 Multi-Docent)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import TenantMembership, User, UserGroupAssignment
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.tenant_mgmt.models import Tenant

TEST_TENANT_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# --- Fixtures ---


@pytest_asyncio.fixture
async def admin_data() -> dict:
    return {
        "email": f"mem-admin-{uuid.uuid4().hex[:8]}@example.com",
        "password": "AdminPass123!",
        "full_name": "Admin User",
    }


@pytest_asyncio.fixture
async def teacher_data() -> dict:
    return {
        "email": f"mem-teacher-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherPass123!",
        "full_name": "Jan Docent",
    }


@pytest_asyncio.fixture
async def parent_data() -> dict:
    return {
        "email": f"mem-parent-{uuid.uuid4().hex[:8]}@example.com",
        "password": "ParentPass123!",
        "full_name": "Karin Ouder",
    }


@pytest_asyncio.fixture
async def members_setup(
    tenant_client: AsyncClient,
    db_session: AsyncSession,
    admin_data: dict,
    teacher_data: dict,
    parent_data: dict,
):
    """Create a tenant with admin, teacher, and parent."""
    users = {}
    for data in [admin_data, teacher_data, parent_data]:
        with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
            resp = await tenant_client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 201
        users[data["email"]] = uuid.UUID(resp.json()["id"])

    admin_id = users[admin_data["email"]]
    teacher_id = users[teacher_data["email"]]
    parent_id = users[parent_data["email"]]

    await db_session.execute(
        update(User)
        .where(User.id.in_([admin_id, teacher_id, parent_id]))
        .values(email_verified=True)
    )
    await db_session.flush()

    tenant = Tenant(id=TEST_TENANT_UUID, name="Members Test School", slug="test", owner_id=admin_id)
    db_session.add(tenant)
    await db_session.flush()

    for uid in [admin_id, teacher_id, parent_id]:
        db_session.add(TenantMembership(user_id=uid, tenant_id=TEST_TENANT_UUID, is_active=True))
    await db_session.flush()

    groups = await create_default_groups(db_session, TEST_TENANT_UUID)
    db_session.add(UserGroupAssignment(user_id=admin_id, group_id=groups["beheerder"].id))
    db_session.add(UserGroupAssignment(user_id=teacher_id, group_id=groups["docent"].id))
    db_session.add(UserGroupAssignment(user_id=parent_id, group_id=groups["ouder"].id))
    await db_session.flush()

    async def login(data: dict) -> dict:
        resp = await tenant_client.post(
            "/api/v1/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return {
        "admin_id": admin_id,
        "teacher_id": teacher_id,
        "parent_id": parent_id,
        "admin_headers": await login(admin_data),
        "teacher_headers": await login(teacher_data),
        "parent_headers": await login(parent_data),
        "admin_email": admin_data["email"],
        "teacher_email": teacher_data["email"],
        "parent_email": parent_data["email"],
    }


# --- Tests ---


@pytest.mark.asyncio
async def test_list_members(tenant_client: AsyncClient, members_setup: dict):
    """List all members returns all three users with groups."""
    ctx = members_setup
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users",
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    user_ids = [m["user_id"] for m in data["items"]]
    assert str(ctx["admin_id"]) in user_ids
    assert str(ctx["teacher_id"]) in user_ids
    assert str(ctx["parent_id"]) in user_ids


@pytest.mark.asyncio
async def test_filter_by_group(tenant_client: AsyncClient, members_setup: dict):
    """Filter by group=docent returns only teachers."""
    ctx = members_setup
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users?group=docent",
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    user_ids = [m["user_id"] for m in data["items"]]
    assert str(ctx["teacher_id"]) in user_ids
    assert str(ctx["parent_id"]) not in user_ids


@pytest.mark.asyncio
async def test_search_by_name(tenant_client: AsyncClient, members_setup: dict):
    """Search by name filters results."""
    ctx = members_setup
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users?q=Jan",
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    names = [m["full_name"] for m in data["items"]]
    assert any("Jan" in n for n in names)


@pytest.mark.asyncio
async def test_pagination(tenant_client: AsyncClient, members_setup: dict):
    """Pagination returns correct subset, total unchanged."""
    ctx = members_setup
    # Get total first
    resp_all = await tenant_client.get(
        "/api/v1/org/test/access/users",
        headers=ctx["admin_headers"],
    )
    total = resp_all.json()["total"]

    # Get page with limit=1 offset=1
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users?limit=1&offset=1",
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == total  # Total unchanged


@pytest.mark.asyncio
async def test_parent_email_privacy(tenant_client: AsyncClient, members_setup: dict):
    """Parent sees their own email but not others' emails."""
    ctx = members_setup
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users",
        headers=ctx["parent_headers"],
    )
    assert resp.status_code == 200
    for member in resp.json()["items"]:
        if member["user_id"] == str(ctx["parent_id"]):
            # Parent sees own email
            assert member["email"] is not None
        else:
            # Parent should NOT see others' emails
            assert member["email"] is None


@pytest.mark.asyncio
async def test_admin_sees_all_emails(tenant_client: AsyncClient, members_setup: dict):
    """Admin (schoolbeheerder with org_settings.view) sees all emails."""
    ctx = members_setup
    resp = await tenant_client.get(
        "/api/v1/org/test/access/users",
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200
    for member in resp.json()["items"]:
        assert member["email"] is not None


@pytest.mark.asyncio
async def test_unauthenticated(tenant_client: AsyncClient):
    """Unauthenticated request returns 401."""
    resp = await tenant_client.get("/api/v1/org/test/access/users")
    assert resp.status_code == 401
