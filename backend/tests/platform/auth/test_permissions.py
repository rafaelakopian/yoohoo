"""Tests for the dynamic permission & group system: registry, group CRUD,
user assignments, effective permissions, require_permission, and data restriction."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import permission_registry
from app.modules.platform.auth.models import (
    GroupPermission,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.tenant_mgmt.models import Tenant


def _t(slug: str, path: str) -> str:
    """Build a tenant-scoped API path: /api/v1/schools/{slug}{path}"""
    return f"/api/v1/schools/{slug}{path}"


# --- Fixtures ---


@pytest_asyncio.fixture
async def perm_tenant(db_session: AsyncSession, verified_user: dict, client: AsyncClient):
    """Create a tenant with default groups, verified_user assigned to schoolbeheerder."""
    # Find verified user
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    slug = f"perm-test-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name="Perm Test School", slug=slug, owner_id=user.id)
    db_session.add(tenant)
    await db_session.flush()

    # Add membership (deprecated role, kept for backward compat)
    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant.id, is_active=True
    )
    db_session.add(membership)
    await db_session.flush()

    # Create default groups
    groups = await create_default_groups(db_session, tenant.id)

    # Assign user to schoolbeheerder group
    admin_group = groups["schoolbeheerder"]
    db_session.add(UserGroupAssignment(user_id=user.id, group_id=admin_group.id))
    await db_session.flush()

    return {
        "tenant": tenant,
        "slug": slug,
        "user": user,
        "groups": groups,
    }


@pytest_asyncio.fixture
async def perm_headers(client: AsyncClient, verified_user: dict, login_with_2fa) -> dict:
    """Auth headers for verified user (superadmin) in permission tests."""
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# =====================================================================
# PermissionRegistry Tests
# =====================================================================


class TestPermissionRegistry:
    def test_modules_registered(self):
        """All expected modules are registered in the permission registry."""
        modules = permission_registry.get_all_modules()
        module_names = {m.module_name for m in modules}
        assert "students" in module_names
        assert "attendance" in module_names
        assert "schedule" in module_names
        assert "notifications" in module_names
        assert "invitations" in module_names
        assert "school_settings" in module_names

    def test_get_all_codenames(self):
        """get_all_codenames returns a non-empty set of valid codenames."""
        codenames = permission_registry.get_all_codenames()
        assert len(codenames) > 0
        assert "students.view" in codenames
        assert "students.create" in codenames
        assert "attendance.view" in codenames
        assert "schedule.view" in codenames
        assert "schedule.manage" in codenames

    def test_get_permission(self):
        """Individual permission lookup works."""
        perm = permission_registry.get_permission("students.view")
        assert perm is not None
        assert perm.codename == "students.view"
        assert perm.module == "students"
        assert perm.label != ""

    def test_get_permission_invalid(self):
        """Invalid codename returns None."""
        assert permission_registry.get_permission("nonexistent.perm") is None

    def test_is_valid_codename(self):
        """is_valid_codename returns True for registered and False for unknown."""
        assert permission_registry.is_valid_codename("students.view") is True
        assert permission_registry.is_valid_codename("fake.perm") is False


# =====================================================================
# Permission Registry API Tests
# =====================================================================


@pytest.mark.asyncio
async def test_registry_endpoint(client: AsyncClient, perm_headers: dict):
    """GET /permissions/registry returns all modules and permissions."""
    resp = await client.get("/api/v1/permissions/registry", headers=perm_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "modules" in data
    assert len(data["modules"]) >= 6

    module_names = {m["module_name"] for m in data["modules"]}
    assert "students" in module_names
    assert "attendance" in module_names


@pytest.mark.asyncio
async def test_registry_requires_auth(client: AsyncClient):
    """GET /permissions/registry requires authentication."""
    resp = await client.get("/api/v1/permissions/registry")
    assert resp.status_code == 401


# =====================================================================
# Group CRUD Tests
# =====================================================================


@pytest.mark.asyncio
async def test_list_groups(client: AsyncClient, perm_headers: dict, perm_tenant):
    """List groups returns the 3 default groups."""
    slug = perm_tenant["slug"]
    resp = await client.get(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
    )
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) >= 3
    slugs = {g["slug"] for g in groups}
    assert "schoolbeheerder" in slugs
    assert "docent" in slugs
    assert "ouder" in slugs


@pytest.mark.asyncio
async def test_create_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Create a custom permission group."""
    slug = perm_tenant["slug"]
    resp = await client.post(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
        json={
            "name": "Assistent",
            "slug": "assistent",
            "description": "Assistent-docent",
            "permissions": ["students.view", "attendance.view"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Assistent"
    assert data["slug"] == "assistent"
    assert data["is_default"] is False
    assert "students.view" in data["permissions"]
    assert "attendance.view" in data["permissions"]
    assert data["user_count"] == 0


@pytest.mark.asyncio
async def test_create_group_invalid_permission(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Cannot create a group with invalid permission codenames."""
    slug = perm_tenant["slug"]
    resp = await client.post(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
        json={
            "name": "Bad Group",
            "slug": "bad-group",
            "permissions": ["nonexistent.perm"],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_group_duplicate_slug(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Cannot create a group with a duplicate slug in the same tenant."""
    slug = perm_tenant["slug"]
    resp = await client.post(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
        json={
            "name": "Schoolbeheerder Copy",
            "slug": "schoolbeheerder",
            "permissions": [],
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Update a group's name and permissions."""
    slug = perm_tenant["slug"]

    # Create a group first
    create_resp = await client.post(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
        json={
            "name": "Te Updaten",
            "slug": "te-updaten",
            "permissions": ["students.view"],
        },
    )
    group_id = create_resp.json()["id"]

    # Update it
    resp = await client.put(
        _t(slug, f"/permissions/groups/{group_id}"),
        headers=perm_headers,
        json={
            "name": "Updated Name",
            "permissions": ["students.view", "students.create", "attendance.view"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert len(data["permissions"]) == 3


@pytest.mark.asyncio
async def test_delete_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Delete a non-default group."""
    slug = perm_tenant["slug"]

    # Create a group
    create_resp = await client.post(
        _t(slug, "/permissions/groups"),
        headers=perm_headers,
        json={"name": "Te Verwijderen", "slug": "te-verwijderen", "permissions": []},
    )
    group_id = create_resp.json()["id"]

    # Delete it
    resp = await client.delete(
        _t(slug, f"/permissions/groups/{group_id}"),
        headers=perm_headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_default_group_fails(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Cannot delete a default group."""
    slug = perm_tenant["slug"]
    admin_group = perm_tenant["groups"]["schoolbeheerder"]

    resp = await client.delete(
        _t(slug, f"/permissions/groups/{admin_group.id}"),
        headers=perm_headers,
    )
    assert resp.status_code == 403


# =====================================================================
# User Assignment Tests
# =====================================================================


@pytest.mark.asyncio
async def test_list_group_users(client: AsyncClient, perm_headers: dict, perm_tenant):
    """List users in a group returns the assigned user."""
    slug = perm_tenant["slug"]
    admin_group = perm_tenant["groups"]["schoolbeheerder"]

    resp = await client.get(
        _t(slug, f"/permissions/groups/{admin_group.id}/users"),
        headers=perm_headers,
    )
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1
    assert any(u["user_id"] == str(perm_tenant["user"].id) for u in users)


@pytest.mark.asyncio
async def test_assign_user_to_group(
    client: AsyncClient, perm_headers: dict, perm_tenant, db_session: AsyncSession
):
    """Assign a new user to a group."""
    slug = perm_tenant["slug"]
    docent_group = perm_tenant["groups"]["docent"]

    # Create a new user
    user_data = {
        "email": f"assign-{uuid.uuid4().hex[:8]}@example.com",
        "password": "AssignPass123!",
        "full_name": "Assign User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    new_user_id = reg_resp.json()["id"]

    # Verify the user
    await db_session.execute(
        update(User).where(User.id == uuid.UUID(new_user_id)).values(email_verified=True)
    )
    await db_session.flush()

    # Assign to docent group
    resp = await client.post(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
        json={"user_id": new_user_id},
    )
    assert resp.status_code == 201

    # Verify in list
    list_resp = await client.get(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
    )
    assert any(u["user_id"] == new_user_id for u in list_resp.json())


@pytest.mark.asyncio
async def test_assign_user_duplicate(
    client: AsyncClient, perm_headers: dict, perm_tenant, db_session: AsyncSession
):
    """Cannot assign a user to the same group twice."""
    slug = perm_tenant["slug"]
    docent_group = perm_tenant["groups"]["docent"]

    # Create a regular (non-superadmin) user
    user_data = {
        "email": f"dup-{uuid.uuid4().hex[:8]}@example.com",
        "password": "DupPass123!",
        "full_name": "Dup User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    new_user_id = reg_resp.json()["id"]
    await db_session.execute(
        update(User).where(User.id == uuid.UUID(new_user_id)).values(email_verified=True)
    )
    await db_session.flush()

    # First assignment should succeed
    resp1 = await client.post(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
        json={"user_id": new_user_id},
    )
    assert resp1.status_code == 201

    # Second assignment should fail with 409
    resp2 = await client.post(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
        json={"user_id": new_user_id},
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_remove_user_from_group(
    client: AsyncClient, perm_headers: dict, perm_tenant, db_session: AsyncSession
):
    """Remove a user from a group."""
    slug = perm_tenant["slug"]
    docent_group = perm_tenant["groups"]["docent"]

    # Create and assign a user
    user_data = {
        "email": f"remove-{uuid.uuid4().hex[:8]}@example.com",
        "password": "RemovePass123!",
        "full_name": "Remove User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    new_user_id = reg_resp.json()["id"]

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(new_user_id)).values(email_verified=True)
    )
    await db_session.flush()

    # Assign
    await client.post(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
        json={"user_id": new_user_id},
    )

    # Remove
    resp = await client.delete(
        _t(slug, f"/permissions/groups/{docent_group.id}/users/{new_user_id}"),
        headers=perm_headers,
    )
    assert resp.status_code == 204

    # Verify removed
    list_resp = await client.get(
        _t(slug, f"/permissions/groups/{docent_group.id}/users"),
        headers=perm_headers,
    )
    assert not any(u["user_id"] == new_user_id for u in list_resp.json())


# =====================================================================
# Effective Permissions Tests
# =====================================================================


@pytest.mark.asyncio
async def test_my_permissions_superadmin(client: AsyncClient, perm_headers: dict, perm_tenant):
    """Superadmin gets all registered permissions."""
    slug = perm_tenant["slug"]
    resp = await client.get(
        _t(slug, "/permissions/my-permissions"),
        headers=perm_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "permissions" in data
    assert "groups" in data
    # Superadmin should have all codenames
    all_codenames = permission_registry.get_all_codenames()
    assert set(data["permissions"]) == all_codenames


@pytest.mark.asyncio
async def test_my_permissions_regular_user(
    client: AsyncClient, db_session: AsyncSession, perm_tenant
):
    """Regular user gets only group-assigned permissions."""
    slug = perm_tenant["slug"]

    # Create a user with only ouder (parent) group
    user_data = {
        "email": f"ouder-{uuid.uuid4().hex[:8]}@example.com",
        "password": "OuderPass123!",
        "full_name": "Ouder User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = uuid.UUID(reg_resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )

    # Add membership and group assignment
    tenant_id = perm_tenant["tenant"].id
    db_session.add(TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=True))
    ouder_group = perm_tenant["groups"]["ouder"]
    db_session.add(UserGroupAssignment(user_id=user_id, group_id=ouder_group.id))
    await db_session.flush()

    # Login as this user
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = await client.get(
        _t(slug, "/permissions/my-permissions"),
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    perms = set(data["permissions"])
    # Ouder group has view_own but NOT students.create
    assert "students.view_own" in perms
    assert "students.create" not in perms
    assert "students.view" not in perms


# =====================================================================
# /me Endpoint with Groups & Permissions
# =====================================================================


@pytest.mark.asyncio
async def test_me_includes_groups_and_permissions(
    client: AsyncClient, perm_headers: dict, perm_tenant
):
    """/me response includes groups and effective permissions per membership."""
    resp = await client.get("/api/v1/auth/me", headers=perm_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "memberships" in data

    tenant_id = str(perm_tenant["tenant"].id)
    membership = next(
        (m for m in data["memberships"] if m["tenant_id"] == tenant_id), None
    )
    # Superadmin may or may not have groups depending on implementation,
    # but permissions should be populated
    assert membership is not None
    assert "groups" in membership
    assert "permissions" in membership
    assert len(membership["permissions"]) > 0


# =====================================================================
# Invitation with group_id
# =====================================================================


@pytest.mark.asyncio
async def test_create_invitation_with_group_id(
    client: AsyncClient, perm_headers: dict, perm_tenant
):
    """Create invitation with group_id instead of role."""
    tenant_id = str(perm_tenant["tenant"].id)
    docent_group = perm_tenant["groups"]["docent"]

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={
                "email": f"group-invite-{uuid.uuid4().hex[:8]}@example.com",
                "group_id": str(docent_group.id),
            },
            headers=perm_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["group_id"] == str(docent_group.id)
    assert data["group_name"] == "Docent"


# =====================================================================
# Admin Group Management (SuperAdmin manages groups per tenant)
# =====================================================================


@pytest.mark.asyncio
async def test_admin_list_groups(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin can list groups for any tenant via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)
    resp = await client.get(
        f"/api/v1/admin/schools/{tenant_id}/groups",
        headers=perm_headers,
    )
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) >= 3
    slugs = {g["slug"] for g in groups}
    assert "schoolbeheerder" in slugs
    assert "docent" in slugs
    assert "ouder" in slugs


@pytest.mark.asyncio
async def test_admin_create_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin can create a group for a tenant via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)
    resp = await client.post(
        f"/api/v1/admin/schools/{tenant_id}/groups",
        headers=perm_headers,
        json={
            "name": "Admin Created",
            "slug": "admin-created",
            "permissions": ["students.view", "attendance.view"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Admin Created"
    assert data["is_default"] is False
    assert "students.view" in data["permissions"]


@pytest.mark.asyncio
async def test_admin_update_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin can update a group's name and permissions via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)

    # Create first
    create_resp = await client.post(
        f"/api/v1/admin/schools/{tenant_id}/groups",
        headers=perm_headers,
        json={"name": "To Update Admin", "slug": "to-update-admin", "permissions": []},
    )
    group_id = create_resp.json()["id"]

    # Update
    resp = await client.put(
        f"/api/v1/admin/schools/{tenant_id}/groups/{group_id}",
        headers=perm_headers,
        json={"name": "Updated by Admin", "permissions": ["schedule.view"]},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated by Admin"
    assert "schedule.view" in resp.json()["permissions"]


@pytest.mark.asyncio
async def test_admin_delete_group(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin can delete a non-default group via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)

    # Create first
    create_resp = await client.post(
        f"/api/v1/admin/schools/{tenant_id}/groups",
        headers=perm_headers,
        json={"name": "To Delete Admin", "slug": "to-delete-admin", "permissions": []},
    )
    group_id = create_resp.json()["id"]

    # Delete
    resp = await client.delete(
        f"/api/v1/admin/schools/{tenant_id}/groups/{group_id}",
        headers=perm_headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_delete_default_group_fails(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin cannot delete a default group via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)
    admin_group = perm_tenant["groups"]["schoolbeheerder"]

    resp = await client.delete(
        f"/api/v1/admin/schools/{tenant_id}/groups/{admin_group.id}",
        headers=perm_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_group_users(client: AsyncClient, perm_headers: dict, perm_tenant):
    """SuperAdmin can list users in a group via admin API."""
    tenant_id = str(perm_tenant["tenant"].id)
    admin_group = perm_tenant["groups"]["schoolbeheerder"]

    resp = await client.get(
        f"/api/v1/admin/schools/{tenant_id}/groups/{admin_group.id}/users",
        headers=perm_headers,
    )
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1
    assert any(u["user_id"] == str(perm_tenant["user"].id) for u in users)


@pytest.mark.asyncio
async def test_admin_groups_requires_superadmin(
    client: AsyncClient, perm_tenant, db_session: AsyncSession
):
    """Non-superadmin cannot access admin group endpoints."""
    # Create a regular user
    user_data = {
        "email": f"nonadmin-{uuid.uuid4().hex[:8]}@example.com",
        "password": "RegularPass123!",
        "full_name": "Regular User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = uuid.UUID(reg_resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    # Login as regular user
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    tenant_id = str(perm_tenant["tenant"].id)
    resp = await client.get(
        f"/api/v1/admin/schools/{tenant_id}/groups",
        headers=headers,
    )
    assert resp.status_code == 403


# =====================================================================
# Platform-Level Permission Groups Tests
# =====================================================================


class TestPlatformPermissionRegistry:
    """Test that platform module is registered and codenames are valid."""

    def test_platform_module_registered(self):
        modules = permission_registry.get_all_modules()
        module_names = {m.module_name for m in modules}
        assert "platform" in module_names

    def test_platform_codenames(self):
        codenames = permission_registry.get_all_codenames()
        assert "platform.view_stats" in codenames
        assert "platform.view_schools" in codenames
        assert "platform.manage_schools" in codenames
        assert "platform.view_users" in codenames
        assert "platform.edit_users" in codenames
        assert "platform.manage_superadmin" in codenames
        assert "platform.manage_memberships" in codenames
        assert "platform.manage_groups" in codenames
        assert "platform.view_audit_logs" in codenames


@pytest.mark.asyncio
async def test_platform_group_crud(client: AsyncClient, perm_headers: dict):
    """SuperAdmin can create, list, get, update, and delete platform groups."""
    # Create
    resp = await client.post(
        "/api/v1/admin/platform-groups",
        headers=perm_headers,
        json={
            "name": "Test Platform Group",
            "slug": "test-platform-group",
            "description": "For testing",
            "permissions": ["platform.view_stats", "platform.view_users"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    group_id = data["id"]
    assert data["name"] == "Test Platform Group"
    assert data["tenant_id"] is None
    assert "platform.view_stats" in data["permissions"]
    assert data["is_default"] is False

    # List
    resp = await client.get(
        "/api/v1/admin/platform-groups",
        headers=perm_headers,
    )
    assert resp.status_code == 200
    groups = resp.json()
    assert any(g["id"] == group_id for g in groups)

    # Get
    resp = await client.get(
        f"/api/v1/admin/platform-groups/{group_id}",
        headers=perm_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == group_id

    # Update
    resp = await client.put(
        f"/api/v1/admin/platform-groups/{group_id}",
        headers=perm_headers,
        json={
            "name": "Updated Platform Group",
            "permissions": ["platform.view_stats", "platform.view_schools", "platform.view_audit_logs"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Platform Group"
    assert len(resp.json()["permissions"]) == 3

    # Delete
    resp = await client.delete(
        f"/api/v1/admin/platform-groups/{group_id}",
        headers=perm_headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_platform_group_user_assignment(
    client: AsyncClient, perm_headers: dict, db_session: AsyncSession
):
    """SuperAdmin can assign/remove users to/from platform groups."""
    # Create platform group
    create_resp = await client.post(
        "/api/v1/admin/platform-groups",
        headers=perm_headers,
        json={
            "name": "Assign Test",
            "slug": f"assign-test-{uuid.uuid4().hex[:6]}",
            "permissions": ["platform.view_stats"],
        },
    )
    group_id = create_resp.json()["id"]

    # Create a user
    user_data = {
        "email": f"platuser-{uuid.uuid4().hex[:8]}@example.com",
        "password": "PlatPass123!",
        "full_name": "Platform User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = reg_resp.json()["id"]

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(user_id)).values(email_verified=True)
    )
    await db_session.flush()

    # Assign user to platform group
    resp = await client.post(
        f"/api/v1/admin/platform-groups/{group_id}/users",
        headers=perm_headers,
        json={"user_id": user_id},
    )
    assert resp.status_code == 201

    # List users
    resp = await client.get(
        f"/api/v1/admin/platform-groups/{group_id}/users",
        headers=perm_headers,
    )
    assert resp.status_code == 200
    assert any(u["user_id"] == user_id for u in resp.json())

    # Remove user
    resp = await client.delete(
        f"/api/v1/admin/platform-groups/{group_id}/users/{user_id}",
        headers=perm_headers,
    )
    assert resp.status_code == 204

    # Verify removed
    resp = await client.get(
        f"/api/v1/admin/platform-groups/{group_id}/users",
        headers=perm_headers,
    )
    assert not any(u["user_id"] == user_id for u in resp.json())

    # Cleanup
    await client.delete(
        f"/api/v1/admin/platform-groups/{group_id}",
        headers=perm_headers,
    )


@pytest.mark.asyncio
async def test_platform_permissions_in_effective(
    client: AsyncClient, db_session: AsyncSession
):
    """User with platform group gets platform permissions in effective set."""
    # Create user
    user_data = {
        "email": f"eff-plat-{uuid.uuid4().hex[:8]}@example.com",
        "password": "EffPlatPass123!",
        "full_name": "Effective Platform User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = uuid.UUID(reg_resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    # Create platform group and assign user
    group = PermissionGroup(
        tenant_id=None,
        name="Effective Test",
        slug=f"eff-test-{uuid.uuid4().hex[:6]}",
        description=None,
        is_default=False,
    )
    db_session.add(group)
    await db_session.flush()

    db_session.add(GroupPermission(group_id=group.id, permission_codename="platform.view_stats"))
    db_session.add(GroupPermission(group_id=group.id, permission_codename="platform.view_users"))
    db_session.add(UserGroupAssignment(user_id=user_id, group_id=group.id))
    await db_session.flush()

    # Login and check /me
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()

    # Should have platform_groups and platform_permissions
    assert len(me_data["platform_groups"]) >= 1
    assert "platform.view_stats" in me_data["platform_permissions"]
    assert "platform.view_users" in me_data["platform_permissions"]

    # Should NOT have tenant permissions (no membership)
    assert me_data["memberships"] == []


@pytest.mark.asyncio
async def test_platform_permission_guard(
    client: AsyncClient, db_session: AsyncSession
):
    """User with platform.view_stats can access /admin/stats."""
    # Create user
    user_data = {
        "email": f"guard-plat-{uuid.uuid4().hex[:8]}@example.com",
        "password": "GuardPlatPass123!",
        "full_name": "Guard Platform User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = uuid.UUID(reg_resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    # Create platform group with view_stats and assign
    group = PermissionGroup(
        tenant_id=None,
        name="Stats Viewer",
        slug=f"stats-viewer-{uuid.uuid4().hex[:6]}",
        is_default=False,
    )
    db_session.add(group)
    await db_session.flush()

    db_session.add(GroupPermission(group_id=group.id, permission_codename="platform.view_stats"))
    db_session.add(UserGroupAssignment(user_id=user_id, group_id=group.id))
    await db_session.flush()

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Can access /admin/stats (has platform.view_stats)
    resp = await client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 200

    # Cannot access /admin/users (missing platform.view_users)
    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403

    # Cannot access /admin/audit-logs (missing platform.view_audit_logs)
    resp = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_bypasses_platform_perms(
    client: AsyncClient, perm_headers: dict
):
    """Superadmin can access all admin endpoints without explicit platform permissions."""
    # Superadmin can access everything
    resp = await client.get("/api/v1/admin/stats", headers=perm_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/admin/users", headers=perm_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/admin/audit-logs", headers=perm_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/admin/schools", headers=perm_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_regular_user_no_platform_access(
    client: AsyncClient, db_session: AsyncSession
):
    """Regular user without platform group cannot access admin endpoints."""
    user_data = {
        "email": f"noplat-{uuid.uuid4().hex[:8]}@example.com",
        "password": "NoPlatPass123!",
        "full_name": "No Platform User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    user_id = uuid.UUID(reg_resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # No platform permissions — all admin endpoints should return 403
    resp = await client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/admin/schools", headers=headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/admin/platform-groups", headers=headers)
    assert resp.status_code == 403
