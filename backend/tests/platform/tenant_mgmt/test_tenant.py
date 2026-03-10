import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Test Piano School", "slug": "test-school"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Piano School"
    assert data["slug"] == "test-school"
    assert data["is_provisioned"] is False


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "School A", "slug": "dup-slug"},
        headers=auth_headers,
    )
    response = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "School B", "slug": "dup-slug"},
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_tenants(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "List School", "slug": "list-school"},
        headers=auth_headers,
    )

    response = await client.get("/api/v1/platform/orgs/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_tenant_settings(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Settings School", "slug": "settings-school"},
        headers=auth_headers,
    )
    tenant_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/platform/orgs/{tenant_id}/settings", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Europe/Amsterdam"
    assert data["academic_year_start_month"] == 8


@pytest.mark.asyncio
async def test_update_tenant_settings(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Update School", "slug": "update-school"},
        headers=auth_headers,
    )
    tenant_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/platform/orgs/{tenant_id}/settings",
        json={"org_name": "Yoohoo Music School", "org_phone": "+31 55 1234567"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["org_name"] == "Yoohoo Music School"
    assert data["org_phone"] == "+31 55 1234567"


@pytest.mark.asyncio
async def test_delete_tenant_not_provisioned(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Delete School", "slug": "delete-school"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    response = await client.request(
        "DELETE",
        f"/api/v1/platform/orgs/{tenant_id}",
        headers=auth_headers,
        json={"password": "TestPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "delete-school"

    # Verify it no longer appears in the list (hard deleted)
    list_resp = await client.get("/api/v1/platform/orgs/", headers=auth_headers)
    slugs = [t["slug"] for t in list_resp.json()]
    assert "delete-school" not in slugs

    # Verify tenant is truly gone (not soft-deleted)
    get_resp = await client.get(
        f"/api/v1/platform/orgs/{tenant_id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_tenant_wrong_password(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Wrong Pwd School", "slug": "wrong-pwd-school"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    response = await client.request(
        "DELETE",
        f"/api/v1/platform/orgs/{tenant_id}",
        headers=auth_headers,
        json={"password": "WrongPassword999!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


@pytest.mark.asyncio
async def test_delete_tenant_unauthenticated(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Unauth Del School", "slug": "unauth-del-school"},
        headers=auth_headers,
    )
    tenant_id = create_resp.json()["id"]

    response = await client.request(
        "DELETE",
        f"/api/v1/platform/orgs/{tenant_id}",
        json={"password": "TestPassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(client: AsyncClient):
    response = await client.post(
        "/api/v1/platform/orgs/",
        json={"name": "Unauth School", "slug": "unauth-school"},
    )
    assert response.status_code == 401
