"""Tests for Support Notes (B4)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.tenant_mgmt.models import Tenant, TenantSettings


# =====================================================================
# Helpers
# =====================================================================


async def _create_tenant(db: AsyncSession, slug: str = "notes-test") -> Tenant:
    tenant = Tenant(name="Notes Test", slug=slug, is_active=True, is_provisioned=False)
    db.add(tenant)
    await db.flush()
    settings = TenantSettings(tenant_id=tenant.id, org_name="Notes Test", org_email=f"info@{slug}.nl")
    db.add(settings)
    await db.flush()
    return tenant


# =====================================================================
# Tenant Notes CRUD
# =====================================================================


@pytest.mark.asyncio
async def test_create_tenant_note(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session)
    resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "Test notitie", "is_pinned": False},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Test notitie"
    assert data["is_pinned"] is False
    assert "created_by_name" in data
    assert "created_by_email" in data
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_list_tenant_notes(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="list-notes")
    # Create two notes
    await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "Note 1"},
    )
    await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "Note 2", "is_pinned": True},
    )

    resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Pinned first
    assert data[0]["is_pinned"] is True
    assert data[0]["content"] == "Note 2"


@pytest.mark.asyncio
async def test_update_own_note(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="update-note")
    create_resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "Original"},
    )
    note_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/admin/operations/notes/{note_id}",
        headers=auth_headers,
        json={"content": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated"
    assert resp.json()["updated_at"] is not None


@pytest.mark.asyncio
async def test_delete_own_note(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="delete-note")
    create_resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "To delete"},
    )
    note_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/admin/operations/notes/{note_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Should no longer appear in listing (soft delete)
    list_resp = await client.get(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
    )
    assert all(n["id"] != note_id for n in list_resp.json())


@pytest.mark.asyncio
async def test_toggle_pin(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="pin-note")
    create_resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "Pin me"},
    )
    note_id = create_resp.json()["id"]
    assert create_resp.json()["is_pinned"] is False

    # Toggle on
    resp = await client.patch(
        f"/api/v1/admin/operations/notes/{note_id}/pin",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_pinned"] is True

    # Toggle off
    resp = await client.patch(
        f"/api/v1/admin/operations/notes/{note_id}/pin",
        headers=auth_headers,
    )
    assert resp.json()["is_pinned"] is False


# =====================================================================
# User Notes
# =====================================================================


@pytest.mark.asyncio
async def test_user_notes_crud(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
    db_session: AsyncSession,
):
    """Create and list notes on a user."""
    from app.modules.platform.auth.models import User
    from sqlalchemy import select

    user = (await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )).scalar_one()

    # Create
    resp = await client.post(
        f"/api/v1/admin/operations/users/{user.id}/notes",
        headers=auth_headers,
        json={"content": "User note"},
    )
    assert resp.status_code == 201

    # List
    resp = await client.get(
        f"/api/v1/admin/operations/users/{user.id}/notes",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert any(n["content"] == "User note" for n in resp.json())


# =====================================================================
# Validation
# =====================================================================


@pytest.mark.asyncio
async def test_note_content_too_long(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="long-note")
    resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": "x" * 5001},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_note_content_empty(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    tenant = await _create_tenant(db_session, slug="empty-note")
    resp = await client.post(
        f"/api/v1/admin/operations/tenants/{tenant.id}/notes",
        headers=auth_headers,
        json={"content": ""},
    )
    assert resp.status_code == 422


# =====================================================================
# Not Found
# =====================================================================


@pytest.mark.asyncio
async def test_update_nonexistent_note(
    client: AsyncClient, auth_headers: dict,
):
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"/api/v1/admin/operations/notes/{fake_id}",
        headers=auth_headers,
        json={"content": "Nope"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_note(
    client: AsyncClient, auth_headers: dict,
):
    fake_id = uuid.uuid4()
    resp = await client.delete(
        f"/api/v1/admin/operations/notes/{fake_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# =====================================================================
# Permission
# =====================================================================


@pytest.mark.asyncio
async def test_notes_require_auth(client: AsyncClient, db_session: AsyncSession):
    tenant = await _create_tenant(db_session, slug="noauth-note")
    resp = await client.get(f"/api/v1/admin/operations/tenants/{tenant.id}/notes")
    assert resp.status_code == 401
