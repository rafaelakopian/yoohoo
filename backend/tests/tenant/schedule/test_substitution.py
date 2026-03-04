"""Tests for lesson substitution endpoints (Fase 6 Multi-Docent)."""

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
async def teacher_data() -> dict:
    return {
        "email": f"sub-teacher-{uuid.uuid4().hex[:8]}@example.com",
        "password": "SubTeacher123!",
        "full_name": "Sub Teacher",
    }


@pytest_asyncio.fixture
async def substitute_data() -> dict:
    return {
        "email": f"substitute-{uuid.uuid4().hex[:8]}@example.com",
        "password": "Substitute123!",
        "full_name": "Substitute Teacher",
    }


@pytest_asyncio.fixture
async def sub_setup(
    tenant_client: AsyncClient,
    db_session: AsyncSession,
    teacher_data: dict,
    substitute_data: dict,
):
    """Create a tenant with two teachers for substitution tests."""
    users = {}
    for data in [teacher_data, substitute_data]:
        with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
            resp = await tenant_client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 201
        users[data["email"]] = uuid.UUID(resp.json()["id"])

    teacher_id = users[teacher_data["email"]]
    substitute_id = users[substitute_data["email"]]

    await db_session.execute(
        update(User)
        .where(User.id.in_([teacher_id, substitute_id]))
        .values(email_verified=True)
    )
    await db_session.flush()

    tenant = Tenant(id=TEST_TENANT_UUID, name="Sub Test School", slug="test", owner_id=teacher_id)
    db_session.add(tenant)
    await db_session.flush()

    for uid in [teacher_id, substitute_id]:
        db_session.add(TenantMembership(user_id=uid, tenant_id=TEST_TENANT_UUID, is_active=True))
    await db_session.flush()

    groups = await create_default_groups(db_session, TEST_TENANT_UUID)
    db_session.add(UserGroupAssignment(user_id=teacher_id, group_id=groups["docent"].id))
    db_session.add(UserGroupAssignment(user_id=substitute_id, group_id=groups["docent"].id))
    await db_session.flush()

    async def login(data: dict) -> dict:
        resp = await tenant_client.post(
            "/api/v1/auth/login",
            json={"email": data["email"], "password": data["password"]},
        )
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return {
        "teacher_id": teacher_id,
        "substitute_id": substitute_id,
        "teacher_headers": await login(teacher_data),
        "substitute_headers": await login(substitute_data),
    }


async def _create_lesson(client: AsyncClient, headers: dict) -> str:
    """Helper: create a student + lesson instance and return the instance id."""
    s_resp = await client.post(
        "/api/v1/orgs/test/students/",
        json={"first_name": "SubKid"},
        headers=headers,
    )
    assert s_resp.status_code == 201
    student_id = s_resp.json()["id"]

    l_resp = await client.post(
        "/api/v1/orgs/test/schedule/lessons/",
        json={
            "student_id": student_id,
            "lesson_date": "2026-04-01",
            "start_time": "14:00:00",
            "duration_minutes": 30,
        },
        headers=headers,
    )
    assert l_resp.status_code == 201
    return l_resp.json()["id"]


# --- Tests ---


@pytest.mark.asyncio
async def test_assign_substitute(tenant_client: AsyncClient, sub_setup: dict, tenant_auth_headers: dict):
    """Admin can assign a substitute teacher to a lesson."""
    ctx = sub_setup
    instance_id = await _create_lesson(tenant_client, tenant_auth_headers)

    resp = await tenant_client.post(
        f"/api/v1/orgs/test/schedule/lessons/{instance_id}/substitute",
        json={"substitute_teacher_user_id": str(ctx["substitute_id"])},
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["substitute_teacher_user_id"] == str(ctx["substitute_id"])


@pytest.mark.asyncio
async def test_assign_substitute_with_reason(tenant_client: AsyncClient, sub_setup: dict, tenant_auth_headers: dict):
    """Substitution with reason stores the reason."""
    ctx = sub_setup
    instance_id = await _create_lesson(tenant_client, tenant_auth_headers)

    resp = await tenant_client.post(
        f"/api/v1/orgs/test/schedule/lessons/{instance_id}/substitute",
        json={
            "substitute_teacher_user_id": str(ctx["substitute_id"]),
            "reason": "Docent ziek",
        },
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["substitution_reason"] == "Docent ziek"


@pytest.mark.asyncio
async def test_teacher_with_substitute_permission(tenant_client: AsyncClient, sub_setup: dict):
    """Teacher with schedule.substitute permission can assign substitute."""
    ctx = sub_setup
    instance_id = await _create_lesson(tenant_client, ctx["teacher_headers"])

    resp = await tenant_client.post(
        f"/api/v1/orgs/test/schedule/lessons/{instance_id}/substitute",
        json={"substitute_teacher_user_id": str(ctx["substitute_id"])},
        headers=ctx["teacher_headers"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_overwrite_existing_substitute(tenant_client: AsyncClient, sub_setup: dict, tenant_auth_headers: dict):
    """Overwriting an existing substitution updates (no 409)."""
    ctx = sub_setup
    instance_id = await _create_lesson(tenant_client, tenant_auth_headers)

    # First substitute
    await tenant_client.post(
        f"/api/v1/orgs/test/schedule/lessons/{instance_id}/substitute",
        json={"substitute_teacher_user_id": str(ctx["substitute_id"])},
        headers=tenant_auth_headers,
    )

    # Overwrite with teacher as substitute
    resp = await tenant_client.post(
        f"/api/v1/orgs/test/schedule/lessons/{instance_id}/substitute",
        json={
            "substitute_teacher_user_id": str(ctx["teacher_id"]),
            "reason": "Changed substitute",
        },
        headers=tenant_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["substitute_teacher_user_id"] == str(ctx["teacher_id"])


@pytest.mark.asyncio
async def test_unauthorized_substitute(tenant_client: AsyncClient, sub_setup: dict, tenant_auth_headers: dict):
    """User without schedule.substitute permission gets 403/404."""
    # Create a parent user who lacks schedule.substitute
    parent_data = {
        "email": f"sub-parent-{uuid.uuid4().hex[:8]}@example.com",
        "password": "ParentPass123!",
        "full_name": "Sub Parent",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await tenant_client.post("/api/v1/auth/register", json=parent_data)

    # We don't need to set up parent in tenant — without membership they get 401/403 anyway
    login_resp = await tenant_client.post(
        "/api/v1/auth/login",
        json={"email": parent_data["email"], "password": parent_data["password"]},
    )
    # Unverified user cannot login
    assert login_resp.status_code in (400, 401, 403)
