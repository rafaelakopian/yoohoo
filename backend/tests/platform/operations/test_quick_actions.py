"""Tests for Quick Actions (B2)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import User


# =====================================================================
# Helpers
# =====================================================================


async def _create_target_user(
    client: AsyncClient, db: AsyncSession,
    email: str = "target@example.com",
    full_name: str = "Target User",
    password: str = "TestPassword123!",
    verified: bool = True,
    active: bool = True,
) -> dict:
    """Create a non-superadmin target user."""
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": full_name,
        })
    assert resp.status_code == 201
    user_data = resp.json()
    uid = uuid.UUID(user_data["id"])

    vals = {"is_superadmin": False}
    if verified:
        vals["email_verified"] = True
    if not active:
        vals["is_active"] = False

    await db.execute(update(User).where(User.id == uid).values(**vals))
    await db.flush()

    return {"id": str(uid), "email": email, "password": password}


# =====================================================================
# Force Password Reset
# =====================================================================


@pytest.mark.asyncio
async def test_force_password_reset(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(client, db_session, email=f"pwd-{uuid.uuid4().hex[:6]}@test.com")

    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/v1/platform/operations/users/{target['id']}/force-password-reset",
            headers=auth_headers,
        )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_force_password_reset_superadmin_blocked(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
    db_session: AsyncSession,
):
    """Cannot force password reset on superadmin."""
    # Get the superadmin user id
    user = (await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )).scalar_one()

    resp = await client.post(
        f"/api/v1/platform/operations/users/{user.id}/force-password-reset",
        headers=auth_headers,
    )
    assert resp.status_code == 403


# =====================================================================
# Toggle Active
# =====================================================================


@pytest.mark.asyncio
async def test_toggle_active_deactivate(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
    db_session: AsyncSession,
):
    target = await _create_target_user(client, db_session, email=f"toggle-{uuid.uuid4().hex[:6]}@test.com")

    resp = await client.post(
        f"/api/v1/platform/operations/users/{target['id']}/toggle-active",
        headers=auth_headers,
        json={"password": verified_user["password"]},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_toggle_active_wrong_password(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(client, db_session, email=f"togglefail-{uuid.uuid4().hex[:6]}@test.com")

    resp = await client.post(
        f"/api/v1/platform/operations/users/{target['id']}/toggle-active",
        headers=auth_headers,
        json={"password": "WrongPassword123!"},
    )
    assert resp.status_code == 403


# =====================================================================
# Resend Verification
# =====================================================================


@pytest.mark.asyncio
async def test_resend_verification(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(
        client, db_session,
        email=f"verify-{uuid.uuid4().hex[:6]}@test.com",
        verified=False,
    )

    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/v1/platform/operations/users/{target['id']}/resend-verification",
            headers=auth_headers,
        )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_resend_verification_already_verified(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(
        client, db_session,
        email=f"already-{uuid.uuid4().hex[:6]}@test.com",
        verified=True,
    )

    resp = await client.post(
        f"/api/v1/platform/operations/users/{target['id']}/resend-verification",
        headers=auth_headers,
    )
    assert resp.status_code == 409


# =====================================================================
# Revoke Sessions
# =====================================================================


@pytest.mark.asyncio
async def test_revoke_sessions(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    target = await _create_target_user(client, db_session, email=f"revoke-{uuid.uuid4().hex[:6]}@test.com")

    resp = await client.post(
        f"/api/v1/platform/operations/users/{target['id']}/revoke-sessions",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "revoked_count" in resp.json()


# =====================================================================
# Disable 2FA
# =====================================================================


@pytest.mark.asyncio
async def test_disable_2fa_not_enabled(
    client: AsyncClient, auth_headers: dict, verified_user: dict,
    db_session: AsyncSession,
):
    """Cannot disable 2FA if not enabled."""
    target = await _create_target_user(
        client, db_session,
        email=f"no2fa-{uuid.uuid4().hex[:6]}@test.com",
    )

    resp = await client.post(
        f"/api/v1/platform/operations/users/{target['id']}/disable-2fa",
        headers=auth_headers,
        json={"password": verified_user["password"]},
    )
    assert resp.status_code == 409


# =====================================================================
# Not Found
# =====================================================================


@pytest.mark.asyncio
async def test_quick_action_user_not_found(
    client: AsyncClient, auth_headers: dict,
):
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/platform/operations/users/{fake_id}/revoke-sessions",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# =====================================================================
# Auth Required
# =====================================================================


@pytest.mark.asyncio
async def test_quick_actions_require_auth(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/platform/operations/users/{fake_id}/revoke-sessions")
    assert resp.status_code == 401
