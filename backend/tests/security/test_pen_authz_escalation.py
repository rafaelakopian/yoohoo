"""PEN-02: Authorization Escalation Tests.

Verifies that regular users cannot access admin/superadmin endpoints,
and that permission boundaries are enforced.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_regular_user(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a verified non-admin user and return login tokens."""
    email = f"regular-{uuid.uuid4().hex[:8]}@example.com"
    password = "RegularPass123!"

    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": "Regular User",
        })
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Verify email but do NOT make superadmin, do NOT enable 2FA
    from app.modules.platform.auth.models import User
    from sqlalchemy import update

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(user_id)).values(
            email_verified=True, is_superadmin=False,
        )
    )
    await db_session.flush()

    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    tokens = login_resp.json()
    return {
        "headers": {"Authorization": f"Bearer {tokens["access_token"]}"},
        "user_id": user_id,
        "email": email,
    }


# ======================================================================
# Regular user cannot access platform admin endpoints
# ======================================================================

ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/platform/dashboard"),
    ("GET", "/api/v1/platform/access/users"),
    ("GET", "/api/v1/platform/audit-logs"),
    ("GET", "/api/v1/platform/operations/dashboard"),
    ("GET", "/api/v1/platform/access/groups"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_regular_user_cannot_access_admin(
    client: AsyncClient, db_session: AsyncSession, method: str, path: str,
):
    """Non-admin users must be rejected from admin endpoints."""
    user = await _create_regular_user(client, db_session)
    response = await client.request(method, path, headers=user["headers"])
    assert response.status_code in (401, 403), (
        f"Regular user accessed {method} {path} — got {response.status_code}"
    )


# ======================================================================
# Regular user cannot toggle superadmin
# ======================================================================

@pytest.mark.asyncio
async def test_regular_user_cannot_toggle_superadmin(
    client: AsyncClient, db_session: AsyncSession,
):
    """Non-admin user cannot promote themselves or others to superadmin."""
    user = await _create_regular_user(client, db_session)
    response = await client.put(
        f"/api/v1/platform/access/users/{user["user_id"]}/superadmin",
        headers=user["headers"],
        json={"is_superadmin": True},
    )
    assert response.status_code in (401, 403)


# ======================================================================
# Regular user cannot manage platform billing
# ======================================================================

BILLING_ADMIN_ENDPOINTS = [
    ("POST", "/api/v1/platform/billing/plans"),
    ("GET", "/api/v1/platform/billing/invoices"),
    ("GET", "/api/v1/platform/billing/payments"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", BILLING_ADMIN_ENDPOINTS)
async def test_regular_user_cannot_access_billing_admin(
    client: AsyncClient, db_session: AsyncSession, method: str, path: str,
):
    """Non-admin users must be rejected from billing admin endpoints."""
    user = await _create_regular_user(client, db_session)
    response = await client.request(method, path, headers=user["headers"])
    assert response.status_code in (401, 403, 422), (
        f"Regular user accessed {method} {path} — got {response.status_code}"
    )


# ======================================================================
# Non-member cannot access tenant-scoped endpoints
# ======================================================================

TENANT_ENDPOINTS = [
    ("GET", "/api/v1/org/test/students/"),
    ("GET", "/api/v1/org/test/attendance/"),
    ("GET", "/api/v1/org/test/schedule/slots/"),
    ("GET", "/api/v1/org/test/notifications/in-app/"),
    ("GET", "/api/v1/org/test/tuition/plans"),
    ("GET", "/api/v1/org/test/access/groups"),
    ("GET", "/api/v1/org/test/collaborations/"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", TENANT_ENDPOINTS)
async def test_non_member_cannot_access_tenant(
    tenant_client: AsyncClient, db_session: AsyncSession, method: str, path: str,
):
    """Users who are not members of a tenant cannot access its resources."""
    user = await _create_regular_user(tenant_client, db_session)
    response = await tenant_client.request(method, path, headers=user["headers"])
    assert response.status_code in (401, 403, 404), (
        f"Non-member accessed {method} {path} — got {response.status_code}"
    )


# ======================================================================
# Non-existent tenant slug
# ======================================================================

@pytest.mark.asyncio
async def test_nonexistent_tenant_slug(client: AsyncClient, auth_headers: dict):
    """Accessing a tenant that doesn't exist must return 404."""
    response = await client.get(
        "/api/v1/org/this-tenant-does-not-exist/students/",
        headers=auth_headers,
    )
    assert response.status_code in (403, 404)


# ======================================================================
# Regular user cannot access operations endpoints
# ======================================================================

@pytest.mark.asyncio
async def test_regular_user_cannot_impersonate(
    client: AsyncClient, db_session: AsyncSession,
):
    """Non-admin user cannot use impersonation."""
    user = await _create_regular_user(client, db_session)
    response = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=user["headers"],
        json={"user_id": user["user_id"], "reason": "test"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_regular_user_cannot_force_password_reset(
    client: AsyncClient, db_session: AsyncSession,
):
    """Non-admin user cannot force password reset on others."""
    user = await _create_regular_user(client, db_session)
    response = await client.post(
        f"/api/v1/platform/operations/users/{user["user_id"]}/force-password-reset",
        headers=user["headers"],
    )
    assert response.status_code in (401, 403)
