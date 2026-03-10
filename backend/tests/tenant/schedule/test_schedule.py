import pytest
from httpx import AsyncClient


async def _create_student(client: AsyncClient, headers: dict) -> str:
    """Helper: create a student and return its id."""
    resp = await client.post(
        "/api/v1/org/test/students/",
        json={"first_name": "Lisa", "last_name": "de Vries"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_slot(client: AsyncClient, headers: dict, student_id: str) -> str:
    """Helper: create a lesson slot and return its id."""
    resp = await client.post(
        "/api/v1/org/test/schedule/slots/",
        json={
            "student_id": student_id,
            "day_of_week": 3,  # Wednesday
            "start_time": "14:00:00",
            "duration_minutes": 30,
            "location": "Lokaal A",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ─── Slot CRUD ───


@pytest.mark.asyncio
async def test_create_slot(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    response = await tenant_client.post(
        "/api/v1/org/test/schedule/slots/",
        json={
            "student_id": student_id,
            "day_of_week": 1,
            "start_time": "10:00:00",
            "duration_minutes": 45,
        },
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == student_id
    assert data["day_of_week"] == 1
    assert data["start_time"] == "10:00:00"
    assert data["duration_minutes"] == 45
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_slots(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    await _create_slot(tenant_client, tenant_auth_headers, student_id)

    response = await tenant_client.get(
        "/api/v1/org/test/schedule/slots/", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_slot(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    slot_id = await _create_slot(tenant_client, tenant_auth_headers, student_id)

    response = await tenant_client.get(
        f"/api/v1/org/test/schedule/slots/{slot_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["id"] == slot_id


@pytest.mark.asyncio
async def test_update_slot(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    slot_id = await _create_slot(tenant_client, tenant_auth_headers, student_id)

    response = await tenant_client.put(
        f"/api/v1/org/test/schedule/slots/{slot_id}",
        json={"duration_minutes": 60, "location": "Lokaal B"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["duration_minutes"] == 60
    assert data["location"] == "Lokaal B"


@pytest.mark.asyncio
async def test_delete_slot(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    slot_id = await _create_slot(tenant_client, tenant_auth_headers, student_id)

    response = await tenant_client.delete(
        f"/api/v1/org/test/schedule/slots/{slot_id}", headers=tenant_auth_headers
    )
    assert response.status_code == 200

    # Verify it's gone
    get_resp = await tenant_client.get(
        f"/api/v1/org/test/schedule/slots/{slot_id}", headers=tenant_auth_headers
    )
    assert get_resp.status_code == 404


# ─── Instance CRUD ───


@pytest.mark.asyncio
async def test_create_lesson_instance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    response = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-03-04",
            "start_time": "15:00:00",
            "duration_minutes": 30,
        },
        headers=tenant_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == student_id
    assert data["lesson_date"] == "2026-03-04"
    assert data["status"] == "scheduled"


@pytest.mark.asyncio
async def test_list_instances_with_filters(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-03-05",
            "start_time": "10:00:00",
        },
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get(
        f"/api/v1/org/test/schedule/lessons/?student_id={student_id}&date_from=2026-03-01&date_to=2026-03-31",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["student_id"] == student_id for item in data["items"])


# ─── Generate instances ───


@pytest.mark.asyncio
async def test_generate_instances(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    # Create a slot for Wednesday
    await tenant_client.post(
        "/api/v1/org/test/schedule/slots/",
        json={
            "student_id": student_id,
            "day_of_week": 3,  # Wednesday
            "start_time": "14:00:00",
            "duration_minutes": 30,
        },
        headers=tenant_auth_headers,
    )

    # Generate for March 2026 (has 4-5 Wednesdays)
    response = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/generate",
        json={"start_date": "2026-03-01", "end_date": "2026-03-31"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["generated"] >= 4
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_generate_instances_skips_holidays(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    # Create a slot for Monday
    await tenant_client.post(
        "/api/v1/org/test/schedule/slots/",
        json={
            "student_id": student_id,
            "day_of_week": 1,  # Monday
            "start_time": "09:00:00",
        },
        headers=tenant_auth_headers,
    )

    # Create a holiday covering all of March
    await tenant_client.post(
        "/api/v1/org/test/schedule/holidays/",
        json={
            "name": "Voorjaarsvakantie",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
        },
        headers=tenant_auth_headers,
    )

    # Generate for April - should skip all due to holiday
    response = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/generate",
        json={"start_date": "2026-04-01", "end_date": "2026-04-30"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["generated"] == 0
    assert data["skipped"] >= 1


@pytest.mark.asyncio
async def test_generate_instances_skips_duplicates(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)

    await tenant_client.post(
        "/api/v1/org/test/schedule/slots/",
        json={
            "student_id": student_id,
            "day_of_week": 4,  # Thursday
            "start_time": "11:00:00",
        },
        headers=tenant_auth_headers,
    )

    # Generate twice for same period
    await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/generate",
        json={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=tenant_auth_headers,
    )
    response = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/generate",
        json={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["generated"] == 0  # All skipped as duplicates
    assert data["skipped"] >= 1


# ─── Cancel + Reschedule ───


@pytest.mark.asyncio
async def test_cancel_instance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    create_resp = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-03-10",
            "start_time": "16:00:00",
        },
        headers=tenant_auth_headers,
    )
    instance_id = create_resp.json()["id"]

    response = await tenant_client.post(
        f"/api/v1/org/test/schedule/lessons/{instance_id}/cancel?reason=Docent+ziek",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["cancellation_reason"] == "Docent ziek"


@pytest.mark.asyncio
async def test_reschedule_instance(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    create_resp = await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-03-11",
            "start_time": "13:00:00",
        },
        headers=tenant_auth_headers,
    )
    instance_id = create_resp.json()["id"]

    response = await tenant_client.post(
        f"/api/v1/org/test/schedule/lessons/{instance_id}/reschedule",
        json={
            "new_date": "2026-03-13",
            "new_time": "14:00:00",
            "reason": "Verplaatst naar vrijdag",
        },
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["lesson_date"] == "2026-03-13"
    assert data["start_time"] == "14:00:00"
    assert data["status"] == "scheduled"

    # Check original is marked as rescheduled
    orig = await tenant_client.get(
        f"/api/v1/org/test/schedule/lessons/{instance_id}", headers=tenant_auth_headers
    )
    assert orig.json()["status"] == "rescheduled"
    assert orig.json()["rescheduled_to_date"] == "2026-03-13"


# ─── Calendar ───


@pytest.mark.asyncio
async def test_calendar_week(tenant_client: AsyncClient, tenant_auth_headers: dict):
    student_id = await _create_student(tenant_client, tenant_auth_headers)
    await tenant_client.post(
        "/api/v1/org/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-03-02",  # Monday
            "start_time": "10:00:00",
        },
        headers=tenant_auth_headers,
    )

    response = await tenant_client.get(
        "/api/v1/org/test/schedule/calendar/week?start=2026-03-02",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-03-02"
    assert data["week_end"] == "2026-03-08"
    assert len(data["lessons"]) >= 1
    assert data["lessons"][0]["student_name"] == "Lisa de Vries"


# ─── Holiday CRUD ───


@pytest.mark.asyncio
async def test_holiday_crud(tenant_client: AsyncClient, tenant_auth_headers: dict):
    # Create
    resp = await tenant_client.post(
        "/api/v1/org/test/schedule/holidays/",
        json={
            "name": "Kerstvakantie",
            "start_date": "2026-12-21",
            "end_date": "2027-01-04",
            "is_recurring": True,
        },
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 201
    holiday_id = resp.json()["id"]

    # List
    list_resp = await tenant_client.get(
        "/api/v1/org/test/schedule/holidays/", headers=tenant_auth_headers
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Update
    upd_resp = await tenant_client.put(
        f"/api/v1/org/test/schedule/holidays/{holiday_id}",
        json={"name": "Kerstvakantie 2026"},
        headers=tenant_auth_headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["name"] == "Kerstvakantie 2026"

    # Delete
    del_resp = await tenant_client.delete(
        f"/api/v1/org/test/schedule/holidays/{holiday_id}", headers=tenant_auth_headers
    )
    assert del_resp.status_code == 200


# ─── Auth ───


@pytest.mark.asyncio
async def test_schedule_unauthenticated(tenant_client: AsyncClient):
    response = await tenant_client.get("/api/v1/org/test/schedule/slots/")
    assert response.status_code == 401
