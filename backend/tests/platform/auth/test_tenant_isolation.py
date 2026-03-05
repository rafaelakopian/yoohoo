"""Tests for tenant data isolation — superadmin cannot access tenant data without membership."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import (
    GroupPermission,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.tenant_mgmt.models import Tenant

from tests.conftest import TEST_TENANT_UUID, _login_with_2fa


# =====================================================================
# Helpers
# =====================================================================

async def _get_user(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def _ensure_test_tenant(db: AsyncSession) -> None:
    """Ensure the test tenant record exists."""
    result = await db.execute(select(Tenant).where(Tenant.id == TEST_TENANT_UUID))
    if not result.scalar_one_or_none():
        db.add(Tenant(
            id=TEST_TENANT_UUID, name="Test Tenant", slug="test",
            is_active=True, is_provisioned=True,
        ))
        await db.flush()


async def _add_membership_with_all_perms(
    db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID,
) -> None:
    """Create membership + beheerder group with all permissions."""
    from app.core.permissions import permission_registry

    membership = TenantMembership(
        user_id=user_id, tenant_id=tenant_id, is_active=True,
    )
    db.add(membership)
    await db.flush()

    group = PermissionGroup(
        tenant_id=tenant_id, name="Beheerder", slug="beheerder-iso",
        is_default=True,
    )
    db.add(group)
    await db.flush()

    for codename in permission_registry.get_all_codenames():
        db.add(GroupPermission(group_id=group.id, permission_codename=codename))
    await db.flush()

    db.add(UserGroupAssignment(user_id=user_id, group_id=group.id))
    await db.flush()


# =====================================================================
# Tests
# =====================================================================


@pytest.mark.asyncio
async def test_superadmin_blocked_from_tenant_without_membership(
    tenant_client: AsyncClient, verified_user: dict, db_session: AsyncSession,
):
    """Superadmin without TenantMembership cannot access tenant-scoped endpoints."""
    # Login as superadmin (has NO membership in test tenant)
    tokens = await _login_with_2fa(tenant_client, verified_user["email"], verified_user["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Try to access tenant-scoped students endpoint
    response = await tenant_client.get("/api/v1/orgs/test/students/", headers=headers)
    # Should be 403 (no membership) or 404 (hidden)
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_superadmin_with_membership_can_access_tenant(
    tenant_client: AsyncClient, verified_user: dict, db_session: AsyncSession,
):
    """Superadmin WITH TenantMembership can access tenant-scoped endpoints."""
    await _ensure_test_tenant(db_session)
    user = await _get_user(db_session, verified_user["email"])
    await _add_membership_with_all_perms(db_session, user.id, TEST_TENANT_UUID)

    tokens = await _login_with_2fa(tenant_client, verified_user["email"], verified_user["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await tenant_client.get("/api/v1/orgs/test/students/", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_superadmin_platform_endpoints_still_work(
    client: AsyncClient, auth_headers: dict,
):
    """Superadmin can still access platform-scoped endpoints (no tenant context)."""
    response = await client.get("/api/v1/admin/stats", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_superadmin_operations_endpoints_still_work(
    client: AsyncClient, auth_headers: dict,
):
    """Superadmin can still access operations endpoints (platform-scoped)."""
    response = await client.get(
        "/api/v1/admin/operations/dashboard", headers=auth_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_regular_user_without_membership_blocked(
    tenant_client: AsyncClient, db_session: AsyncSession,
):
    """Non-superadmin without membership is blocked (existing behavior preserved)."""
    from unittest.mock import AsyncMock, patch

    user_data = {
        "email": f"regular-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TestPassword123!",
        "full_name": "Regular User",
    }

    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await tenant_client.post("/api/v1/auth/register", json=user_data)
    assert resp.status_code == 201

    # Verify the user in DB (not superadmin, no membership)
    from sqlalchemy import update
    await db_session.execute(
        update(User).where(User.email == user_data["email"]).values(email_verified=True)
    )
    await db_session.flush()

    login_resp = await tenant_client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    tokens = login_resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await tenant_client.get("/api/v1/orgs/test/students/", headers=headers)
    assert response.status_code in (403, 404)
