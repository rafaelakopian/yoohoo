"""Tests for teacher-student assignment endpoints (Fase 6 Multi-Docent)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import TenantMembership, User, UserGroupAssignment
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.tenant_mgmt.models import Tenant

TEST_TENANT_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# --- Fixtures ---


@pytest_asyncio.fixture
async def teacher_a_data() -> dict:
    return {
        "email": f"teacher-a-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherA123!",
        "full_name": "Teacher Alpha",
    }


@pytest_asyncio.fixture
async def teacher_b_data() -> dict:
    return {
        "email": f"teacher-b-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherB123!",
        "full_name": "Teacher Bravo",
    }


@pytest_asyncio.fixture
async def parent_data() -> dict:
    return {
        "email": f"parent-ta-{uuid.uuid4().hex[:8]}@example.com",
        "password": "ParentPass123!",
        "full_name": "Parent User",
    }


@pytest_asyncio.fixture
async def multi_teacher_setup(
    tenant_client: AsyncClient,
    db_session: AsyncSession,
    teacher_a_data: dict,
    teacher_b_data: dict,
    parent_data: dict,
):
    """Create a tenant with two teachers and one parent."""
    users = {}
    for data in [teacher_a_data, teacher_b_data, parent_data]:
        with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
            resp = await tenant_client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 201
        users[data["email"]] = uuid.UUID(resp.json()["id"])

    teacher_a_id = users[teacher_a_data["email"]]
    teacher_b_id = users[teacher_b_data["email"]]
    parent_id = users[parent_data["email"]]

    # Verify all users
    await db_session.execute(
        update(User)
        .where(User.id.in_([teacher_a_id, teacher_b_id, parent_id]))
        .values(email_verified=True)
    )
    await db_session.flush()

    # Create tenant
    tenant = Tenant(id=TEST_TENANT_UUID, name="Assignment Test School", slug="test", owner_id=teacher_a_id)
    db_session.add(tenant)
    await db_session.flush()

    # Memberships
    for uid in [teacher_a_id, teacher_b_id, parent_id]:
        db_session.add(TenantMembership(user_id=uid, tenant_id=TEST_TENANT_UUID, is_active=True))
    await db_session.flush()

    # Permission groups
    groups = await create_default_groups(db_session, TEST_TENANT_UUID)
    db_session.add(UserGroupAssignment(user_id=teacher_a_id, group_id=groups["docent"].id))
    db_session.add(UserGroupAssignment(user_id=teacher_b_id, group_id=groups["docent"].id))
    db_session.add(UserGroupAssignment(user_id=parent_id, group_id=groups["ouder"].id))
    await db_session.flush()

    # Login all users
    async def login(data: dict) -> dict:
        resp = await tenant_client.post(
            "/api/v1/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return {
        "tenant_id": TEST_TENANT_UUID,
        "teacher_a_id": teacher_a_id,
        "teacher_b_id": teacher_b_id,
        "parent_id": parent_id,
        "teacher_a_headers": await login(teacher_a_data),
        "teacher_b_headers": await login(teacher_b_data),
        "parent_headers": await login(parent_data),
    }


async def _create_student(client: AsyncClient, headers: dict, name: str = "TestStudent") -> str:
    resp = await client.post(
        "/api/v1/org/test/students/",
        json={"first_name": name},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# --- Tests ---


@pytest.mark.asyncio
async def test_self_assign(tenant_client: AsyncClient, multi_teacher_setup: dict):
    """Teacher can self-assign to an unassigned student."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "SelfAssignKid")

    resp = await tenant_client.post(
        f"/api/v1/org/test/students/self-assign/{student_id}",
        headers=ctx["teacher_a_headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == str(ctx["teacher_a_id"])

    # Verify student is in my-students
    list_resp = await tenant_client.get(
        "/api/v1/org/test/students/my-students",
        headers=ctx["teacher_a_headers"],
    )
    assert list_resp.status_code == 200
    assert any(s["id"] == student_id for s in list_resp.json()["items"])


@pytest.mark.asyncio
async def test_self_assign_already_assigned_conflict(tenant_client: AsyncClient, multi_teacher_setup: dict):
    """Self-assign to an already-assigned student returns 409."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "AlreadyAssigned")

    # Assign via teacher A
    await tenant_client.post(
        f"/api/v1/org/test/students/self-assign/{student_id}",
        headers=ctx["teacher_a_headers"],
    )

    # Teacher B tries self-assign → conflict because student already has a teacher
    resp = await tenant_client.post(
        f"/api/v1/org/test/students/self-assign/{student_id}",
        headers=ctx["teacher_b_headers"],
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_assign_teacher(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Admin can assign a teacher to a student via POST /{id}/teachers."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "AdminAssign")

    resp = await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == str(ctx["teacher_a_id"])


@pytest.mark.asyncio
async def test_duplicate_assign_conflict(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Assigning the same teacher twice returns 409."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "DuplicateAssign")

    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )

    resp = await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_multi_teacher_assign(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Multiple teachers can be assigned to the same student."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "MultiTeacher")

    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )
    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_b_id"])},
        headers=tenant_auth_headers,
    )

    # List teachers for student
    resp = await tenant_client.get(
        f"/api/v1/org/test/students/{student_id}/teachers",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    teacher_ids = [t["user_id"] for t in resp.json()["items"]]
    assert str(ctx["teacher_a_id"]) in teacher_ids
    assert str(ctx["teacher_b_id"]) in teacher_ids


@pytest.mark.asyncio
async def test_unassign_leaves_other(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Unassigning teacher A leaves teacher B's assignment intact."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "UnassignTest")

    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )
    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_b_id"])},
        headers=tenant_auth_headers,
    )

    # Unassign teacher A
    resp = await tenant_client.delete(
        f"/api/v1/org/test/students/{student_id}/teachers/{ctx['teacher_a_id']}",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 204

    # Teacher B still assigned
    list_resp = await tenant_client.get(
        f"/api/v1/org/test/students/{student_id}/teachers",
        headers=tenant_auth_headers,
    )
    teacher_ids = [t["user_id"] for t in list_resp.json()["items"]]
    assert str(ctx["teacher_b_id"]) in teacher_ids
    assert str(ctx["teacher_a_id"]) not in teacher_ids

    # Teacher A's my-students no longer has this student
    my_resp = await tenant_client.get(
        "/api/v1/org/test/students/my-students",
        headers=ctx["teacher_a_headers"],
    )
    assert not any(s["id"] == student_id for s in my_resp.json()["items"])


@pytest.mark.asyncio
async def test_transfer_student(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Transfer student from teacher A to teacher B."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "TransferKid")

    # Assign to teacher A
    await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=tenant_auth_headers,
    )

    # Transfer to teacher B
    resp = await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/transfer",
        json={
            "from_teacher_user_id": str(ctx["teacher_a_id"]),
            "to_teacher_user_id": str(ctx["teacher_b_id"]),
        },
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200

    # Teacher B has student, teacher A doesn't
    teachers_resp = await tenant_client.get(
        f"/api/v1/org/test/students/{student_id}/teachers",
        headers=tenant_auth_headers,
    )
    teacher_ids = [t["user_id"] for t in teachers_resp.json()["items"]]
    assert str(ctx["teacher_b_id"]) in teacher_ids
    assert str(ctx["teacher_a_id"]) not in teacher_ids


@pytest.mark.asyncio
async def test_list_unassigned(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Unassigned endpoint returns students without teachers."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "Unassigned")

    resp = await tenant_client.get(
        "/api/v1/org/test/students/unassigned",
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["items"]]
    assert student_id in ids


@pytest.mark.asyncio
async def test_parent_cannot_assign(
    tenant_client: AsyncClient, multi_teacher_setup: dict
):
    """Parent cannot assign teachers."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "ParentNoAssign")

    resp = await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_a_id"])},
        headers=ctx["parent_headers"],
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_teacher_datascope_assigned_only(
    tenant_client: AsyncClient, multi_teacher_setup: dict, tenant_auth_headers: dict
):
    """Teacher only sees students assigned to them in main list."""
    ctx = multi_teacher_setup

    # Create two students, assign only one to teacher A
    s1_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "Assigned")
    await _create_student(tenant_client, ctx["teacher_a_headers"], "NotAssigned")

    await tenant_client.post(
        f"/api/v1/org/test/students/self-assign/{s1_id}",
        headers=ctx["teacher_a_headers"],
    )

    # Teacher A list → should see assigned student only
    resp = await tenant_client.get(
        "/api/v1/org/test/students/",
        headers=ctx["teacher_a_headers"],
    )
    assert resp.status_code == 200
    names = [s["first_name"] for s in resp.json()["items"]]
    assert "Assigned" in names
    # NotAssigned should not be visible to this teacher
    assert "NotAssigned" not in names


@pytest.mark.asyncio
async def test_teacher_assign_permission(
    tenant_client: AsyncClient, multi_teacher_setup: dict
):
    """Teacher with students.assign can assign another teacher via endpoint."""
    ctx = multi_teacher_setup
    student_id = await _create_student(tenant_client, ctx["teacher_a_headers"], "TeacherAssign")

    # Teacher A assigns teacher B (docent has students.assign)
    resp = await tenant_client.post(
        f"/api/v1/org/test/students/{student_id}/teachers",
        json={"user_id": str(ctx["teacher_b_id"])},
        headers=ctx["teacher_a_headers"],
    )
    assert resp.status_code == 201
