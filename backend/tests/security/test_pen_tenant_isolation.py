"""PEN-03: Tenant Isolation Tests.

Verifies that users from one tenant cannot access another tenant's data.
Cross-tenant data leakage is a critical multi-tenant security concern.

NOTE: These tests use `client` (not `tenant_client`) so the real
resolve_tenant_from_path dependency runs and rejects unknown slugs.
"""

import uuid

import pytest
from httpx import AsyncClient


# ======================================================================
# Cross-tenant access attempts (real path resolution, no mock)
# ======================================================================

CROSS_TENANT_ENDPOINTS = [
    ("GET", "/api/v1/org/other-school/students/"),
    ("GET", "/api/v1/org/other-school/attendance/"),
    ("GET", "/api/v1/org/other-school/schedule/slots/"),
    ("GET", "/api/v1/org/other-school/notifications/in-app/"),
    ("GET", "/api/v1/org/other-school/tuition/plans"),
    ("GET", "/api/v1/org/other-school/access/groups"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", CROSS_TENANT_ENDPOINTS)
async def test_user_cannot_access_nonexistent_tenant(
    client: AsyncClient, auth_headers: dict, method: str, path: str,
):
    """Accessing a non-existent tenant slug must return 404."""
    response = await client.request(method, path, headers=auth_headers)
    assert response.status_code in (403, 404), (
        f"{method} {path} returned {response.status_code} for unknown tenant"
    )


@pytest.mark.asyncio
async def test_cannot_create_student_in_nonexistent_tenant(
    client: AsyncClient, auth_headers: dict,
):
    """Cannot create a student in a tenant that does not exist."""
    response = await client.post(
        "/api/v1/org/other-school/students/",
        headers=auth_headers,
        json={"first_name": "Evil", "last_name": "Student"},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cannot_modify_nonexistent_tenant_settings(
    client: AsyncClient, auth_headers: dict,
):
    """Cannot modify settings of a tenant that does not exist."""
    fake_tenant_id = str(uuid.uuid4())
    response = await client.put(
        f"/api/v1/platform/orgs/{fake_tenant_id}/settings",
        headers=auth_headers,
        json={"name": "Hacked School"},
    )
    assert response.status_code in (403, 404, 422)


# ======================================================================
# Tenant slug manipulation
# ======================================================================

SLUG_INJECTION_PAYLOADS = [
    "../admin",
    "test/../../admin",
    "test%2F..%2Fadmin",
    "test; DROP TABLE",
    "<script>alert(1)</script>",
    "a" * 500,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", SLUG_INJECTION_PAYLOADS)
async def test_malicious_slug_rejected(
    client: AsyncClient, auth_headers: dict, slug: str,
):
    """Malicious tenant slugs must not cause errors or bypass isolation."""
    response = await client.get(
        f"/api/v1/org/{slug}/students/",
        headers=auth_headers,
    )
    assert response.status_code in (400, 403, 404, 405, 422), (
        f"Slug returned unexpected {response.status_code}"
    )


# ======================================================================
# Cross-tenant write attempts (using real path resolution)
# ======================================================================

@pytest.mark.asyncio
async def test_cannot_invite_to_nonexistent_tenant(
    client: AsyncClient, auth_headers: dict,
):
    """Cannot send invitations for a tenant that does not exist."""
    response = await client.post(
        "/api/v1/org/nonexistent-school/access/invitations",
        headers=auth_headers,
        json={"email": "victim@example.com", "group_id": str(uuid.uuid4())},
    )
    assert response.status_code in (403, 404, 422)


@pytest.mark.asyncio
async def test_cannot_manage_nonexistent_tenant_groups(
    client: AsyncClient, auth_headers: dict,
):
    """Cannot create permission groups in a tenant that does not exist."""
    response = await client.post(
        "/api/v1/org/other-school/access/groups",
        headers=auth_headers,
        json={"name": "Evil Group", "slug": "evil", "permissions": ["students.view"]},
    )
    assert response.status_code in (403, 404)


# ======================================================================
# Own-tenant access works (positive control)
# ======================================================================

@pytest.mark.asyncio
async def test_own_tenant_access_works(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Sanity check: user CAN access their own tenant."""
    response = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
