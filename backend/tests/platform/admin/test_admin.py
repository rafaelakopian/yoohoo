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
    response = await client.get("/api/v1/platform/dashboard", headers=regular_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_success(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/platform/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_tenants" in data
    assert "active_subscriptions" in data
    assert "total_users" in data
    assert "active_users" in data


# --- Admin Tenants ---

@pytest.mark.asyncio
async def test_admin_list_tenants_enriched(client: AsyncClient, auth_headers: dict):
    """Admin gets enriched tenant list with owner_name and member_count."""
    response = await client.get("/api/v1/platform/orgs/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Admin response includes enriched fields
    if len(data) > 0:
        assert "owner_name" in data[0]
        assert "member_count" in data[0]


@pytest.mark.asyncio
async def test_regular_user_list_tenants_no_enrichment(client: AsyncClient, regular_auth_headers: dict):
    """Regular user gets basic tenant list (only their own orgs)."""
    response = await client.get("/api/v1/platform/orgs/", headers=regular_auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# --- Toggle Superadmin ---

@pytest.mark.asyncio
async def test_admin_toggle_superadmin(client: AsyncClient, auth_headers: dict, regular_user: dict):
    # Make superadmin
    response = await client.put(
        f"/api/v1/platform/access/users/{regular_user['id']}/superadmin",
        headers=auth_headers,
        json={"is_superadmin": True},
    )
    assert response.status_code == 200
    assert response.json()["is_superadmin"] is True

    # Revoke superadmin
    response = await client.put(
        f"/api/v1/platform/access/users/{regular_user['id']}/superadmin",
        headers=auth_headers,
        json={"is_superadmin": False},
    )
    assert response.status_code == 200
    assert response.json()["is_superadmin"] is False


# --- Tenant Router Security ---

@pytest.mark.asyncio
async def test_tenant_create_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    response = await client.post(
        "/api/v1/platform/orgs/",
        headers=regular_auth_headers,
        json={"name": "Test School", "slug": "test-school"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_provision_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/platform/orgs/{fake_id}/provision",
        headers=regular_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_delete_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = await client.request(
        "DELETE",
        f"/api/v1/platform/orgs/{fake_id}",
        headers=regular_auth_headers,
        json={"password": "anything"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_get_requires_membership(client: AsyncClient, auth_headers: dict, regular_auth_headers: dict):
    # Admin creates a tenant
    response = await client.post(
        "/api/v1/platform/orgs/",
        headers=auth_headers,
        json={"name": "Private School", "slug": f"private-{uuid.uuid4().hex[:6]}"},
    )
    assert response.status_code == 201
    tenant_id = response.json()["id"]

    # Regular user cannot access it
    response = await client.get(
        f"/api/v1/platform/orgs/{tenant_id}",
        headers=regular_auth_headers,
    )
    assert response.status_code == 403


# --- Audit Logs ---

@pytest.mark.asyncio
async def test_admin_audit_logs_list(client: AsyncClient, auth_headers: dict):
    """Superadmin can list audit logs (login creates audit entries)."""
    response = await client.get("/api/v1/platform/audit-logs", headers=auth_headers)
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
        "/api/v1/platform/audit-logs?action=user.login",
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
        "/api/v1/platform/audit-logs?date_from=2020-01-01T00:00:00&date_to=2099-12-31T23:59:59",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_admin_audit_logs_pagination(client: AsyncClient, auth_headers: dict):
    """Audit logs support pagination."""
    response = await client.get(
        "/api/v1/platform/audit-logs?skip=0&limit=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_category(client: AsyncClient, auth_headers: dict):
    """Can filter audit logs by category (action prefix)."""
    response = await client.get(
        "/api/v1/platform/audit-logs?category=user",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["action"].startswith("user.")


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_category_empty(client: AsyncClient, auth_headers: dict):
    """Category filter with nonexistent category returns empty list."""
    response = await client.get(
        "/api/v1/platform/audit-logs?category=nonexistent_xyz",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_admin_audit_logs_requires_superadmin(client: AsyncClient, regular_auth_headers: dict):
    """Regular user cannot access audit logs."""
    response = await client.get("/api/v1/platform/audit-logs", headers=regular_auth_headers)
    assert response.status_code == 403


# --- Platform Users ---


@pytest.mark.asyncio
async def test_list_platform_users(client: AsyncClient, auth_headers: dict):
    """Superadmin verschijnt in platform users lijst."""
    response = await client.get(
        "/api/v1/platform/access/users", headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(u["is_superadmin"] for u in data)
    item = data[0]
    for field in ("id", "email", "full_name", "platform_groups",
                  "is_superadmin", "created_at"):
        assert field in item


@pytest.mark.asyncio
async def test_list_platform_users_requires_permission(
    client: AsyncClient, regular_auth_headers: dict,
):
    response = await client.get(
        "/api/v1/platform/access/users", headers=regular_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_users(
    client: AsyncClient, auth_headers: dict, regular_user: dict,
):
    query = regular_user["email"][:5]
    response = await client.get(
        f"/api/v1/platform/access/users/search?q={query}", headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(u["email"] == regular_user["email"] for u in data)


@pytest.mark.asyncio
async def test_search_users_min_length(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/platform/access/users/search?q=a", headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_users_requires_permission(
    client: AsyncClient, regular_auth_headers: dict,
):
    response = await client.get(
        "/api/v1/platform/access/users/search?q=test", headers=regular_auth_headers,
    )
    assert response.status_code == 403
