import pytest
from httpx import AsyncClient


async def _create_student(client: AsyncClient, headers: dict) -> str:
    """Helper: create a student and return its id."""
    resp = await client.post(
        "/api/v1/org/test/students/",
        json={"first_name": "Anna", "last_name": "Bakker"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    response = await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-02-27",
            "status": "present",
            "notes": "Goed geoefend",
        },
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == student_id
    assert data["lesson_date"] == "2026-02-27"
    assert data["status"] == "present"
    assert data["notes"] == "Goed geoefend"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-02-20", "status": "present"},
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get("/api/v1/org/test/attendance/", headers=tenant_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_filter_by_date(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-01-10", "status": "present"},
        headers=tenant_auth_headers,
    )
    await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-03-15", "status": "absent"},
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get(
        "/api/v1/org/test/attendance/?date_from=2026-03-01&date_to=2026-03-31",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["lesson_date"] >= "2026-03-01" for item in data["items"])
    assert all(item["lesson_date"] <= "2026-03-31" for item in data["items"])


@pytest.mark.asyncio
async def test_filter_by_student(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    # Create another student
    resp2 = await tenant_client.post(
        "/api/v1/org/test/students/",
        json={"first_name": "Bram"},
        headers=tenant_auth_headers,
    )
    other_id = resp2.json()["id"]

    await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-02-05", "status": "present"},
        headers=tenant_auth_headers,
    )
    await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": other_id, "lesson_date": "2026-02-05", "status": "sick"},
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get(
        f"/api/v1/org/test/attendance/?student_id={student_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["student_id"] == student_id for item in data["items"])


@pytest.mark.asyncio
async def test_get_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    create_resp = await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-02-12", "status": "sick"},
        headers=tenant_auth_headers,
    )
    record_id = create_resp.json()["id"]

    response = await tenant_client.get(
        f"/api/v1/org/test/attendance/{record_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sick"
    assert data["student_id"] == student_id


@pytest.mark.asyncio
async def test_update_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    create_resp = await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-02-13", "status": "absent"},
        headers=tenant_auth_headers,
    )
    record_id = create_resp.json()["id"]

    response = await tenant_client.put(
        f"/api/v1/org/test/attendance/{record_id}",
        json={"status": "excused", "notes": "Ouders hadden gebeld"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "excused"
    assert data["notes"] == "Ouders hadden gebeld"


@pytest.mark.asyncio
async def test_delete_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    create_resp = await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={"student_id": student_id, "lesson_date": "2026-02-14", "status": "present"},
        headers=tenant_auth_headers,
    )
    record_id = create_resp.json()["id"]

    response = await tenant_client.delete(
        f"/api/v1/org/test/attendance/{record_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200

    # Verify it's gone
    get_resp = await tenant_client.get(
        f"/api/v1/org/test/attendance/{record_id}", headers=tenant_auth_headers
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_create_attendance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    # Create two students
    resp1 = await tenant_client.post(
        "/api/v1/org/test/students/",
        json={"first_name": "Eva"},
        headers=tenant_auth_headers,
    )
    resp2 = await tenant_client.post(
        "/api/v1/org/test/students/",
        json={"first_name": "Lars"},
        headers=tenant_auth_headers,
    )
    sid1 = resp1.json()["id"]
    sid2 = resp2.json()["id"]

    response = await tenant_client.post(
        "/api/v1/org/test/attendance/bulk",
        json={
            "lesson_date": "2026-02-26",
            "records": [
                {"student_id": sid1, "status": "present"},
                {"student_id": sid2, "status": "absent", "notes": "Niet gekomen"},
            ],
        },
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2
    assert data["updated"] == 0
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_create_attendance_unauthenticated(tenant_client: AsyncClient):
    response = await tenant_client.post(
        "/api/v1/org/test/attendance/",
        json={
            "student_id": "00000000-0000-0000-0000-000000000000",
            "lesson_date": "2026-02-27",
            "status": "present",
        },
    )
    assert response.status_code == 401
