import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import TenantMembership, User, UserGroupAssignment
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.tenant_mgmt.models import Tenant

# Must match the TEST_TENANT_UUID used by tenant_client fixture in conftest
TEST_TENANT_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# --- Helper fixtures ---


@pytest_asyncio.fixture
async def parent_user_data() -> dict:
    return {
        "email": f"parent-{uuid.uuid4().hex[:8]}@example.com",
        "password": "ParentPass123!",
        "full_name": "Parent User",
    }


@pytest_asyncio.fixture
async def teacher_user_data() -> dict:
    return {
        "email": f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherPass123!",
        "full_name": "Teacher User",
    }


@pytest_asyncio.fixture
async def tenant_with_parent(
    tenant_client: AsyncClient,
    db_session: AsyncSession,
    parent_user_data: dict,
    teacher_user_data: dict,
):
    """Create a tenant with a teacher and a parent user, using group-based permissions."""
    # Register both users first
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await tenant_client.post("/api/v1/auth/register", json=teacher_user_data)
    assert resp.status_code == 201
    teacher_id = uuid.UUID(resp.json()["id"])

    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await tenant_client.post("/api/v1/auth/register", json=parent_user_data)
    assert resp.status_code == 201
    parent_id = uuid.UUID(resp.json()["id"])

    # Verify both users
    await db_session.execute(
        update(User).where(User.id.in_([teacher_id, parent_id])).values(email_verified=True)
    )
    await db_session.flush()

    # Create tenant with TEST_TENANT_UUID to match tenant_client mock
    tenant = Tenant(id=TEST_TENANT_UUID, name="Test School", slug="test", owner_id=teacher_id)
    db_session.add(tenant)
    await db_session.flush()
    tenant_id = tenant.id

    # Create memberships (role=None, group-based now)
    db_session.add(TenantMembership(user_id=teacher_id, tenant_id=tenant_id, is_active=True))
    db_session.add(TenantMembership(user_id=parent_id, tenant_id=tenant_id, is_active=True))
    await db_session.flush()

    # Create default permission groups
    groups = await create_default_groups(db_session, tenant_id)

    # Assign teacher to docent group
    db_session.add(UserGroupAssignment(user_id=teacher_id, group_id=groups["docent"].id))

    # Assign parent to ouder group
    db_session.add(UserGroupAssignment(user_id=parent_id, group_id=groups["ouder"].id))
    await db_session.flush()

    # Login teacher
    login_resp = await tenant_client.post(
        "/api/v1/auth/login",
        json={"email": teacher_user_data["email"], "password": teacher_user_data["password"]},
    )
    teacher_headers = {
        "Authorization": f"Bearer {login_resp.json()['access_token']}",
    }

    # Login parent
    login_resp = await tenant_client.post(
        "/api/v1/auth/login",
        json={"email": parent_user_data["email"], "password": parent_user_data["password"]},
    )
    parent_headers = {
        "Authorization": f"Bearer {login_resp.json()['access_token']}",
    }

    return {
        "tenant_id": tenant_id,
        "teacher_id": teacher_id,
        "parent_id": parent_id,
        "teacher_headers": teacher_headers,
        "parent_headers": parent_headers,
    }


# --- Tests ---


@pytest.mark.asyncio
async def test_teacher_can_create_student(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Teacher (docent group) can create a student."""
    resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "TestKind", "last_name": "Jansen"},
        headers=tenant_with_parent["teacher_headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["first_name"] == "TestKind"


@pytest.mark.asyncio
async def test_parent_cannot_create_student(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Parent (ouder group) should not be able to create a student (hidden=True → 404)."""
    resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Illegal"},
        headers=tenant_with_parent["parent_headers"],
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_parent_cannot_update_student(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Parent should not be able to update a student."""
    # Create a student as teacher
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Kind"},
        headers=tenant_with_parent["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    resp = await tenant_client.put(
        f"/api/v1/schools/test/students/{student_id}",
        json={"first_name": "Hacked"},
        headers=tenant_with_parent["parent_headers"],
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_parent_cannot_delete_student(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Parent should not be able to delete a student."""
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Kind"},
        headers=tenant_with_parent["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    resp = await tenant_client.delete(
        f"/api/v1/schools/test/students/{student_id}",
        headers=tenant_with_parent["parent_headers"],
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_link_and_list_parent_children(
    tenant_client: AsyncClient,
    tenant_with_parent: dict,
    tenant_auth_headers: dict,
):
    """Admin can link a parent to a student, parent sees only linked children."""
    ctx = tenant_with_parent

    # Create two students as teacher
    r1 = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Anna"},
        headers=ctx["teacher_headers"],
    )
    student1_id = r1.json()["id"]

    r2 = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Ben"},
        headers=ctx["teacher_headers"],
    )
    student2_id = r2.json()["id"]

    # Link parent to student1 only (using tenant_auth_headers which is admin-level)
    link_resp = await tenant_client.post(
        f"/api/v1/schools/test/students/{student1_id}/parents",
        json={"user_id": str(ctx["parent_id"]), "student_id": student1_id},
        headers=tenant_auth_headers,
    )
    assert link_resp.status_code == 201
    assert link_resp.json()["student_id"] == student1_id

    # Parent lists students → should see only Anna
    list_resp = await tenant_client.get(
        "/api/v1/schools/test/students/my-children",
        headers=ctx["parent_headers"],
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    names = [s["first_name"] for s in data["items"]]
    assert "Anna" in names
    assert "Ben" not in names


@pytest.mark.asyncio
async def test_unlinked_parent_sees_empty_list(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """A parent with no linked children sees an empty list."""
    resp = await tenant_client.get(
        "/api/v1/schools/test/students/my-children",
        headers=tenant_with_parent["parent_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_parent_cannot_access_unlinked_student(
    tenant_client: AsyncClient,
    tenant_with_parent: dict,
):
    """Parent cannot GET a student they are not linked to."""
    ctx = tenant_with_parent

    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Geheim"},
        headers=ctx["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    resp = await tenant_client.get(
        f"/api/v1/schools/test/students/{student_id}",
        headers=ctx["parent_headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_teacher_sees_assigned_students(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Teacher (view_assigned) sees students assigned to them."""
    ctx = tenant_with_parent

    r1 = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Student1"},
        headers=ctx["teacher_headers"],
    )
    student1_id = r1.json()["id"]

    r2 = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Student2"},
        headers=ctx["teacher_headers"],
    )
    student2_id = r2.json()["id"]

    # Self-assign teacher to both students
    await tenant_client.post(
        f"/api/v1/schools/test/students/self-assign/{student1_id}",
        headers=ctx["teacher_headers"],
    )
    await tenant_client.post(
        f"/api/v1/schools/test/students/self-assign/{student2_id}",
        headers=ctx["teacher_headers"],
    )

    resp = await tenant_client.get(
        "/api/v1/schools/test/students/my-students",
        headers=ctx["teacher_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


@pytest.mark.asyncio
async def test_unlink_parent(
    tenant_client: AsyncClient,
    tenant_with_parent: dict,
    tenant_auth_headers: dict,
):
    """Admin can unlink a parent from a student."""
    ctx = tenant_with_parent

    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "Unlink"},
        headers=ctx["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    # Link
    await tenant_client.post(
        f"/api/v1/schools/test/students/{student_id}/parents",
        json={"user_id": str(ctx["parent_id"]), "student_id": student_id},
        headers=tenant_auth_headers,
    )

    # Verify parent can see student
    resp = await tenant_client.get(
        "/api/v1/schools/test/students/my-children",
        headers=ctx["parent_headers"],
    )
    assert any(s["first_name"] == "Unlink" for s in resp.json()["items"])

    # Unlink
    del_resp = await tenant_client.delete(
        f"/api/v1/schools/test/students/{student_id}/parents/{ctx['parent_id']}",
        headers=tenant_auth_headers,
    )
    assert del_resp.status_code == 204

    # Parent no longer sees student
    resp = await tenant_client.get(
        "/api/v1/schools/test/students/my-children",
        headers=ctx["parent_headers"],
    )
    assert not any(s["first_name"] == "Unlink" for s in resp.json()["items"])


@pytest.mark.asyncio
async def test_parent_attendance_filtering(
    tenant_client: AsyncClient,
    tenant_with_parent: dict,
    tenant_auth_headers: dict,
):
    """Parent can only see attendance of linked children."""
    ctx = tenant_with_parent

    # Create student and link to parent
    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "AttChild"},
        headers=ctx["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    await tenant_client.post(
        f"/api/v1/schools/test/students/{student_id}/parents",
        json={"user_id": str(ctx["parent_id"]), "student_id": student_id},
        headers=tenant_auth_headers,
    )

    # Create attendance record as teacher
    att_resp = await tenant_client.post(
        "/api/v1/schools/test/attendance/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-02-27",
            "status": "present",
        },
        headers=ctx["teacher_headers"],
    )
    assert att_resp.status_code == 201

    # Parent can see attendance
    list_resp = await tenant_client.get(
        f"/api/v1/schools/test/attendance/?student_id={student_id}",
        headers=ctx["parent_headers"],
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_parent_cannot_create_attendance(
    tenant_client: AsyncClient, tenant_with_parent: dict
):
    """Parent cannot create attendance records."""
    ctx = tenant_with_parent

    create_resp = await tenant_client.post(
        "/api/v1/schools/test/students/",
        json={"first_name": "NoAttend"},
        headers=ctx["teacher_headers"],
    )
    student_id = create_resp.json()["id"]

    resp = await tenant_client.post(
        "/api/v1/schools/test/attendance/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-02-27",
            "status": "present",
        },
        headers=ctx["parent_headers"],
    )
    assert resp.status_code in (403, 404)
