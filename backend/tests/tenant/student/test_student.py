import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_student(tenant_client: AsyncClient, tenant_auth_headers: dict):
    response = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Emma", "last_name": "de Vries", "lesson_day": "Dinsdag"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Emma"
    assert data["last_name"] == "de Vries"
    assert data["lesson_day"] == "Dinsdag"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_students(tenant_client: AsyncClient, tenant_auth_headers: dict):
    # Create a student first
    await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Liam"},
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get("/api/v1/schools/test/students/", headers=tenant_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_student(tenant_client: AsyncClient, tenant_auth_headers: dict):
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Sophie", "lesson_duration": 45},
        headers=tenant_auth_headers,
    )
    student_id = create_resp.json()["id"]

    response = await tenant_client.get(
        f"/api/v1/schools/test/students/{student_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Sophie"
    assert data["lesson_duration"] == 45


@pytest.mark.asyncio
async def test_update_student(tenant_client: AsyncClient, tenant_auth_headers: dict):
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Noah", "lesson_day": "Dinsdag"},
        headers=tenant_auth_headers,
    )
    student_id = create_resp.json()["id"]

    response = await tenant_client.put(
        f"/api/v1/schools/test/students/{student_id}",
        json={"lesson_day": "Vrijdag", "lesson_duration": 60},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["lesson_day"] == "Vrijdag"
    assert data["lesson_duration"] == 60
    assert data["first_name"] == "Noah"


@pytest.mark.asyncio
async def test_delete_student(tenant_client: AsyncClient, tenant_auth_headers: dict):
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Julia"},
        headers=tenant_auth_headers,
    )
    student_id = create_resp.json()["id"]

    response = await tenant_client.delete(
        f"/api/v1/schools/test/students/{student_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_create_student_unauthenticated(tenant_client: AsyncClient):
    response = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Unauthorized"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_students(tenant_client: AsyncClient, tenant_auth_headers: dict):
    await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Mirjam", "last_name": "Bakker"},
        headers=tenant_auth_headers,
    )
    await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Pieter", "last_name": "Jansen"},
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get(
        "/api/v1/schools/test/students/?search=Mirjam", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(s["first_name"] == "Mirjam" for s in data["items"])
