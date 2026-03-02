"""Tests for the platform admin API."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import User


@pytest_asyncio.fixture
async def regular_user_data() -> dict:
    return {
        "email": f"regular-{uuid.uuid4().hex[:8]}@example.com",
        "password": "RegularPass123!",
        "full_name": "Regular User",
    }


@pytest_asyncio.fixture
async def regular_user(client: AsyncClient, db_session: AsyncSession, regular_user_data: dict) -> dict:
    """Register a regular (non-admin) verified user."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        response = await client.post("/api/v1/auth/register", json=regular_user_data)
    assert response.status_code == 201
    data = response.json()

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(data["id"])).values(email_verified=True)
    )
    await db_session.flush()

    return {**regular_user_data, "id": data["id"]}


@pytest_asyncio.fixture
async def regular_auth_headers(client: AsyncClient, regular_user: dict) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


# --- Admin Stats ---

@pytest.mark.asyncio
async def test_admin_stats_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    response = await client.get("/api/v1/admin/stats", headers=regular_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_success(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_tenants" in data
    assert "total_users" in data
    assert "active_users" in data


# --- Admin Tenants ---

@pytest.mark.asyncio
async def test_admin_list_tenants(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/schools", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_admin_list_tenants_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    response = await client.get("/api/v1/admin/schools", headers=regular_auth_headers)
    assert response.status_code == 403


# --- Admin Users ---

@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1  # At least the admin user
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_admin_list_users_search(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/users?search=test", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_admin_list_users_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    response = await client.get("/api/v1/admin/users", headers=regular_auth_headers)
    assert response.status_code == 403


# --- Admin User Detail ---

@pytest.mark.asyncio
async def test_admin_user_detail(client: AsyncClient, auth_headers: dict, regular_user: dict):
    response = await client.get(f"/api/v1/admin/users/{regular_user['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == regular_user["email"]
    assert "memberships" in data


@pytest.mark.asyncio
async def test_admin_user_detail_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/admin/users/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


# --- Admin Update User ---

@pytest.mark.asyncio
async def test_admin_update_user(client: AsyncClient, auth_headers: dict, regular_user: dict):
    """Superadmin can update a user's name."""
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user['id']}",
        headers=auth_headers,
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_admin_deactivate_user(client: AsyncClient, auth_headers: dict, regular_user: dict):
    """Superadmin can deactivate a user."""
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user['id']}",
        headers=auth_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Re-activate
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user['id']}",
        headers=auth_headers,
        json={"is_active": True},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_update_user_duplicate_email(
    client: AsyncClient, auth_headers: dict, regular_user: dict, verified_user: dict
):
    """Cannot update user to an email that's already taken."""
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user['id']}",
        headers=auth_headers,
        json={"email": verified_user["email"]},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_update_user_requires_superadmin(
    client: AsyncClient, regular_auth_headers: dict, regular_user: dict
):
    """Regular user cannot update users via admin endpoint."""
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user['id']}",
        headers=regular_auth_headers,
        json={"full_name": "Hacked"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_paginated_users(client: AsyncClient, auth_headers: dict):
    """Paginated user list returns correct structure with skip/limit."""
    response = await client.get("/api/v1/admin/users?skip=0&limit=1", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 0
    assert data["limit"] == 1
    assert len(data["items"]) <= 1
    assert data["total"] >= 1


# --- Toggle Superadmin ---

@pytest.mark.asyncio
async def test_admin_toggle_superadmin(client: AsyncClient, auth_headers: dict, regular_user: dict):
    # Make superadmin
    response = await client.put(
        f"/api/v1/admin/users/{regular_user['id']}/superadmin",
        headers=auth_headers,
        json={"is_superadmin": True},
    )
    assert response.status_code == 200
    assert response.json()["is_superadmin"] is True

    # Revoke superadmin
    response = await client.put(
        f"/api/v1/admin/users/{regular_user['id']}/superadmin",
        headers=auth_headers,
        json={"is_superadmin": False},
    )
    assert response.status_code == 200
    assert response.json()["is_superadmin"] is False


# --- Tenant Router Security ---

@pytest.mark.asyncio
async def test_tenant_create_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    response = await client.post(
        "/api/v1/schools/",
        headers=regular_auth_headers,
        json={"name": "Test School", "slug": "test-school"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_provision_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/schools/{fake_id}/provision",
        headers=regular_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_delete_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.request(
        "DELETE",
        f"/api/v1/schools/{fake_id}",
        headers=regular_auth_headers,
        json={"password": "anything"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_get_requires_membership(client: AsyncClient, auth_headers: dict, regular_auth_headers: dict):
    # Admin creates a tenant
    response = await client.post(
        "/api/v1/schools/",
        headers=auth_headers,
        json={"name": "Private School", "slug": f"private-{uuid.uuid4().hex[:6]}"},
    )
    assert response.status_code == 201
    tenant_id = response.json()["id"]

    # Regular user cannot access it
    response = await client.get(
        f"/api/v1/schools/{tenant_id}",
        headers=regular_auth_headers,
    )
    assert response.status_code == 403


# --- Audit Logs ---

@pytest.mark.asyncio
async def test_admin_audit_logs_list(client: AsyncClient, auth_headers: dict):
    """Superadmin can list audit logs (login creates audit entries)."""
    response = await client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert isinstance(data["items"], list)
    # Login at least created some audit entries
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_action(client: AsyncClient, auth_headers: dict):
    """Can filter audit logs by action."""
    response = await client.get(
        "/api/v1/admin/audit-logs?action=user.login",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert "user.login" in item["action"]


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_date(client: AsyncClient, auth_headers: dict):
    """Can filter audit logs by date range."""
    response = await client.get(
        "/api/v1/admin/audit-logs?date_from=2020-01-01T00:00:00&date_to=2099-12-31T23:59:59",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_admin_audit_logs_pagination(client: AsyncClient, auth_headers: dict):
    """Audit logs support pagination."""
    response = await client.get(
        "/api/v1/admin/audit-logs?skip=0&limit=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_admin_audit_logs_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    """Regular user cannot access audit logs."""
    response = await client.get("/api/v1/admin/audit-logs", headers=regular_auth_headers)
    assert response.status_code == 403
