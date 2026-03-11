"""Tests that cross-tenant access is blocked on ALL tenant-scoped endpoints.

Verifies that users without a TenantMembership for the target tenant
receive 404 (hidden=True) on feature, billing, permissions, and
subscription-status endpoints.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import User


@pytest_asyncio.fixture
async def outsider_headers(
    tenant_client: AsyncClient, db_session: AsyncSession
) -> dict:
    """Auth headers for a verified user who has NO TenantMembership."""
    email = f"outsider-{uuid.uuid4().hex[:8]}@example.com"

    with patch(
        "app.modules.platform.auth.core.service.send_email",
        new_callable=AsyncMock,
    ):
        resp = await tenant_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "TestPassword123!",
                "full_name": "Outsider User",
            },
        )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Verify email directly (no superadmin, no TOTP → simple login)
    await db_session.execute(
        update(User)
        .where(User.id == uuid.UUID(user_id))
        .values(email_verified=True)
    )
    await db_session.flush()

    login_resp = await tenant_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPassword123!"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_feature_status_requires_membership(
    tenant_client: AsyncClient,
    outsider_headers: dict,
):
    """User without TenantMembership gets 404 on GET /org/{slug}/features."""
    response = await tenant_client.get(
        "/api/v1/org/test/features",
        headers=outsider_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_platform_invoices_requires_membership(
    tenant_client: AsyncClient,
    outsider_headers: dict,
):
    """User without TenantMembership gets 404 on GET /org/{slug}/billing/platform-invoices."""
    response = await tenant_client.get(
        "/api/v1/org/test/billing/platform-invoices",
        headers=outsider_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_subscription_status_requires_membership(
    tenant_client: AsyncClient,
    outsider_headers: dict,
):
    """User without TenantMembership gets 404 on GET /org/{slug}/subscription-status."""
    response = await tenant_client.get(
        "/api/v1/org/test/subscription-status",
        headers=outsider_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_my_permissions_requires_membership(
    tenant_client: AsyncClient,
    outsider_headers: dict,
):
    """User without TenantMembership gets 404 on GET /org/{slug}/access/permissions."""
    response = await tenant_client.get(
        "/api/v1/org/test/access/permissions",
        headers=outsider_headers,
    )
    assert response.status_code == 404
