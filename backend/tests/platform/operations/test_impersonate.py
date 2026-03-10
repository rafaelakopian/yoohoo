"""Tests for Impersonation (B1)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import TenantMembership, User
from app.modules.platform.tenant_mgmt.models import Tenant


# =====================================================================
# Helpers
# =====================================================================


async def _create_target_user(
    client: AsyncClient, db: AsyncSession,
    email: str = "target@example.com",
    full_name: str = "Target User",
    password: str = "TestPassword123!",
    active: bool = True,
) -> dict:
    """Create a non-superadmin target user."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": full_name,
        })
    assert resp.status_code == 201
    user_data = resp.json()
    uid = uuid.UUID(user_data["id"])

    vals: dict = {"is_superadmin": False, "email_verified": True}
    if not active:
        vals["is_active"] = False
    await db.execute(update(User).where(User.id == uid).values(**vals))
    await db.flush()

    return {"id": str(uid), "email": email, "password": password, "full_name": full_name}


async def _create_tenant_with_membership(
    db: AsyncSession, user_id: uuid.UUID,
) -> Tenant:
    """Create a tenant and add user as member."""
    slug = f"imp-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name="Impersonate Test", slug=slug, is_active=True, is_provisioned=False)
    db.add(tenant)
    await db.flush()

    membership = TenantMembership(user_id=user_id, tenant_id=tenant.id, is_active=True)
    db.add(membership)
    await db.flush()

    return tenant


# =====================================================================
# Impersonate Endpoint
# =====================================================================


@pytest.mark.asyncio
async def test_impersonate_success(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(
        client, db_session, email=f"imp-{uuid.uuid4().hex[:6]}@test.com",
    )
    tenant = await _create_tenant_with_membership(db_session, uuid.UUID(target["id"]))

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={
            "user_id": target["id"],
            "reason": "Klant kan rooster niet zien",
            "tenant_id": str(tenant.id),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["target_user_email"] == target["email"]
    assert data["target_user_name"] == target["full_name"]
    assert "expires_at" in data
    assert "impersonation_id" in data


@pytest.mark.asyncio
async def test_impersonate_token_works(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Impersonation token can be used to call /me."""
    target = await _create_target_user(
        client, db_session, email=f"imp-{uuid.uuid4().hex[:6]}@test.com",
    )

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": target["id"], "reason": "Testing impersonation"},
    )
    assert resp.status_code == 200
    imp_token = resp.json()["access_token"]

    # Use impersonation token to call /me
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == target["email"]


@pytest.mark.asyncio
async def test_impersonate_self_blocked(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
    db_session: AsyncSession,
):
    """Cannot impersonate yourself."""
    user = (await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )).scalar_one()

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": str(user.id), "reason": "Self impersonation test"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_superadmin_blocked(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot impersonate another superadmin."""
    # Create a superadmin target
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": f"sa-{uuid.uuid4().hex[:6]}@test.com",
            "password": "TestPassword123!",
            "full_name": "Other Superadmin",
        })
    uid = uuid.UUID(resp.json()["id"])
    await db_session.execute(
        update(User).where(User.id == uid).values(
            is_superadmin=True, email_verified=True,
        )
    )
    await db_session.flush()

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": str(uid), "reason": "Trying to impersonate superadmin"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_inactive_user_blocked(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot impersonate inactive user."""
    target = await _create_target_user(
        client, db_session,
        email=f"inactive-{uuid.uuid4().hex[:6]}@test.com",
        active=False,
    )

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": target["id"], "reason": "Inactive user test"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_wrong_tenant(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot impersonate into a tenant the user is not a member of."""
    target = await _create_target_user(
        client, db_session, email=f"imp-{uuid.uuid4().hex[:6]}@test.com",
    )

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={
            "user_id": target["id"],
            "reason": "Wrong tenant test",
            "tenant_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_reason_too_short(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Reason must be at least 5 characters."""
    target = await _create_target_user(
        client, db_session, email=f"imp-{uuid.uuid4().hex[:6]}@test.com",
    )

    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": target["id"], "reason": "Hi"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_impersonate_user_not_found(
    client: AsyncClient, auth_headers: dict,
):
    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        headers=auth_headers,
        json={"user_id": str(uuid.uuid4()), "reason": "User not found test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impersonate_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/platform/operations/impersonate",
        json={"user_id": str(uuid.uuid4()), "reason": "No auth test"},
    )
    assert resp.status_code == 401
