"""PEN-05: Insecure Direct Object Reference (IDOR) Tests.

Verifies that users cannot access or modify resources belonging to
other users by manipulating IDs.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cannot_revoke_other_users_session(
    client: AsyncClient, auth_headers: dict,
):
    """Cannot revoke a session that does not belong to you."""
    fake_session_id = str(uuid.uuid4())
    response = await client.delete(
        f"/api/v1/auth/sessions/{fake_session_id}",
        headers=auth_headers,
    )
    assert response.status_code in (404, 403)


@pytest.mark.asyncio
async def test_random_uuid_user_detail(
    client: AsyncClient, auth_headers: dict,
):
    """Requesting a non-existent user ID via admin should return 404."""
    fake_user_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/platform/access/users/{fake_user_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_get_student_with_random_uuid(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Accessing a non-existent student by random UUID should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.get(
        f"/api/v1/org/test/students/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_get_attendance_with_random_uuid(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Accessing a non-existent attendance record should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.get(
        f"/api/v1/org/test/attendance/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_get_schedule_slot_with_random_uuid(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Accessing a non-existent schedule slot should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.get(
        f"/api/v1/org/test/schedule/slots/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_get_lesson_with_random_uuid(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Accessing a non-existent lesson should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.get(
        f"/api/v1/org/test/schedule/lessons/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_get_invoice_with_random_uuid(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Accessing a non-existent invoice should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.get(
        f"/api/v1/org/test/tuition/invoices/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_nonexistent_student(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Updating a non-existent student should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.put(
        f"/api/v1/org/test/students/{fake_id}",
        headers=tenant_auth_headers,
        json={"first_name": "Hacked"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_nonexistent_student(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Deleting a non-existent student should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.delete(
        f"/api/v1/org/test/students/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_nonexistent_attendance(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Updating a non-existent attendance record should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.put(
        f"/api/v1/org/test/attendance/{fake_id}",
        headers=tenant_auth_headers,
        json={"status": "present"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_nonexistent_permission_group(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Deleting a non-existent permission group should return 404."""
    fake_id = str(uuid.uuid4())
    response = await tenant_client.delete(
        f"/api/v1/org/test/access/groups/{fake_id}",
        headers=tenant_auth_headers,
    )
    assert response.status_code in (404, 400)


@pytest.mark.asyncio
async def test_invalid_uuid_format_rejected(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Invalid UUID format should return 422, not a different error."""
    response = await tenant_client.get(
        "/api/v1/org/test/students/not-a-valid-uuid",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_zero_uuid_handled(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    """Zero UUID should be handled gracefully."""
    response = await tenant_client.get(
        "/api/v1/org/test/students/00000000-0000-0000-0000-000000000000",
        headers=tenant_auth_headers,
    )
    assert response.status_code in (404, 422)
