"""Tests for the User Management System (UMS): invitations, password reset,
change password, sessions, 2FA, and audit logging."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.models import (
    AuditLog,
    Invitation,
    PasswordResetToken,
    RefreshToken,
    TenantMembership,
    User,
)
from app.modules.platform.tenant_mgmt.models import Tenant


# --- Helper fixtures ---


@pytest_asyncio.fixture
async def school_admin_data() -> dict:
    return {
        "email": f"schooladmin-{uuid.uuid4().hex[:8]}@example.com",
        "password": "SchoolAdmin123!",
        "full_name": "School Admin",
    }


@pytest_asyncio.fixture
async def teacher_data() -> dict:
    return {
        "email": f"teacher-ums-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherPass123!",
        "full_name": "Teacher UMS",
    }


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession, verified_user: dict, client: AsyncClient, auth_headers: dict):
    """Create a test tenant and membership for verified_user as school_admin."""
    slug = f"ums-test-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name="UMS Test School", slug=slug)
    db_session.add(tenant)
    await db_session.flush()

    # Find verified user
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    # Add school_admin membership
    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant.id, role=Role.SCHOOL_ADMIN
    )
    db_session.add(membership)
    await db_session.flush()

    return {"tenant": tenant, "user": user}


# =====================================================================
# Invitation Tests (12)
# =====================================================================


@pytest.mark.asyncio
async def test_create_invitation(client: AsyncClient, auth_headers: dict, test_tenant):
    """School admin can create an invitation."""
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "invite1@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "invite1@example.com"
    assert data["role"] == "teacher"


@pytest.mark.asyncio
async def test_list_invitations(client: AsyncClient, auth_headers: dict, test_tenant):
    """School admin can list pending invitations."""
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "list-test@example.com", "role": "teacher"},
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/v1/schools/{tenant_id}/invitations",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_invitation_privilege_escalation(
    client: AsyncClient, db_session: AsyncSession, test_tenant
):
    """Teacher cannot invite as school_admin (privilege escalation)."""
    # Create a teacher user
    teacher_data = {
        "email": f"teacher-priv-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TeacherPass123!",
        "full_name": "Teacher Priv",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json=teacher_data)
    assert resp.status_code == 201
    teacher_id = uuid.UUID(resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == teacher_id).values(email_verified=True)
    )

    # Add teacher membership
    membership = TenantMembership(
        user_id=teacher_id,
        tenant_id=test_tenant["tenant"].id,
        role=Role.TEACHER,
    )
    db_session.add(membership)
    await db_session.flush()

    # Login as teacher (regular user, no 2FA)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": teacher_data["email"], "password": teacher_data["password"]},
    )
    teacher_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Try to invite as school_admin → should fail (hidden=True returns 404)
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "escalate@example.com", "role": "school_admin"},
            headers=teacher_headers,
        )
    # Invitation endpoint uses hidden=True for security, so unauthorized users get 404
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_create_invitation_duplicate_member(
    client: AsyncClient, auth_headers: dict, test_tenant
):
    """Cannot invite someone already a member."""
    user = test_tenant["user"]
    tenant_id = str(test_tenant["tenant"].id)

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": user.email, "role": "teacher"},
            headers=auth_headers,
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_invitation_duplicate_pending(
    client: AsyncClient, auth_headers: dict, test_tenant
):
    """Cannot create duplicate pending invitation for same email+tenant."""
    tenant_id = str(test_tenant["tenant"].id)
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp1 = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "teacher"},
            headers=auth_headers,
        )
    assert resp1.status_code == 201

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp2 = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "teacher"},
            headers=auth_headers,
        )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_accept_invitation_new_user(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """New user can accept invitation and create account."""
    tenant_id = str(test_tenant["tenant"].id)
    email = f"newuser-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )
    assert resp.status_code == 201

    # Get the token from DB
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()

    # Create a matching raw token
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.flush()

    # Accept as new user
    accept_resp = await client.post(
        "/api/v1/auth/accept-invite",
        json={
            "token": raw_token,
            "password": "NewUserPass123!",
            "full_name": "New User",
        },
    )
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["is_new_user"] is True


@pytest.mark.asyncio
async def test_accept_invitation_existing_user(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Existing user can accept invitation without password."""
    # Register a new user
    user_data = {
        "email": f"existing-{uuid.uuid4().hex[:8]}@example.com",
        "password": "ExistingPass123!",
        "full_name": "Existing User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json=user_data)

    # Verify them
    result = await db_session.execute(
        select(User).where(User.email == user_data["email"])
    )
    user = result.scalar_one()
    user.email_verified = True
    await db_session.flush()

    # Invite them
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": user_data["email"], "role": "teacher"},
            headers=auth_headers,
        )
    assert resp.status_code == 201

    # Get token
    inv_result = await db_session.execute(
        select(Invitation).where(Invitation.email == user_data["email"])
    )
    invitation = inv_result.scalar_one()
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.flush()

    # Accept without password
    accept_resp = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["is_new_user"] is False


@pytest.mark.asyncio
async def test_accept_expired_invitation(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Expired invitation cannot be accepted."""
    tenant_id = str(test_tenant["tenant"].id)
    email = f"expired-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "teacher"},
            headers=auth_headers,
        )

    # Expire it
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invitation.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "password": "Pass123!", "full_name": "Test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoke_invitation(client: AsyncClient, auth_headers: dict, test_tenant):
    """School admin can revoke an invitation."""
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        create_resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": f"revoke-{uuid.uuid4().hex[:8]}@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    inv_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/schools/{tenant_id}/invitations/{inv_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resend_invitation(client: AsyncClient, auth_headers: dict, test_tenant):
    """School admin can resend an invitation."""
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        create_resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": f"resend-{uuid.uuid4().hex[:8]}@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    inv_id = create_resp.json()["id"]

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations/{inv_id}/resend",
            headers=auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invite_info(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Public invite-info endpoint returns school and role info."""
    tenant_id = str(test_tenant["tenant"].id)
    email = f"info-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "teacher"},
            headers=auth_headers,
        )

    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invite-info?token={raw_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["school_name"] == "UMS Test School"
    assert data["role"] == "teacher"
    assert data["email"] == email


@pytest.mark.asyncio
async def test_accept_revoked_invitation(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Revoked invitation cannot be accepted."""
    tenant_id = str(test_tenant["tenant"].id)
    email = f"revoked-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        create_resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": email, "role": "teacher"},
            headers=auth_headers,
        )
    inv_id = create_resp.json()["id"]

    # Revoke it
    await client.delete(
        f"/api/v1/schools/{tenant_id}/invitations/{inv_id}",
        headers=auth_headers,
    )

    # Get token hash and create matching raw token
    result = await db_session.execute(
        select(Invitation).where(Invitation.id == uuid.UUID(inv_id))
    )
    invitation = result.scalar_one()
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "password": "Test123!", "full_name": "Test"},
    )
    assert resp.status_code == 401


# =====================================================================
# Password Reset Tests (6)
# =====================================================================


@pytest.mark.asyncio
async def test_forgot_password_valid(client: AsyncClient, verified_user: dict):
    """Forgot password with valid email always returns same response."""
    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": verified_user["email"]},
        )
    assert resp.status_code == 200
    assert "resetlink" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_unknown_email(client: AsyncClient):
    """Forgot password with unknown email returns same response (no enumeration)."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_valid(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Reset password with valid token succeeds."""
    # Create a reset token
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    reset_token = PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )
    db_session.add(reset_token)
    await db_session.flush()

    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "NewPassword123!"},
        )
    assert resp.status_code == 200

    # Can login with new password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user["email"], "password": "NewPassword123!"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_expired(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Reset with expired token fails."""
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(reset_token)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPass123!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_used_token(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Reset with already-used token fails."""
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        used=True,
    )
    db_session.add(reset_token)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPass123!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_same_response(client: AsyncClient, verified_user: dict):
    """Both valid and invalid emails return the same message (no enumeration)."""
    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp1 = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": verified_user["email"]},
        )
        resp2 = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
    assert resp1.json()["message"] == resp2.json()["message"]


# =====================================================================
# Change Password Tests (3)
# =====================================================================


@pytest.mark.asyncio
async def test_change_password_success(
    client: AsyncClient, verified_user: dict, auth_headers: dict
):
    """Authenticated user can change password."""
    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": verified_user["password"],
                "new_password": "BrandNewPassword123!",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    client: AsyncClient, auth_headers: dict
):
    """Change password with wrong current password fails."""
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword!", "new_password": "NewPass123!"},
        headers=auth_headers,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_invalidates_sessions(
    client: AsyncClient, verified_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """Changing password revokes all existing refresh tokens."""
    # Get user
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    user_id = user.id  # capture before expire_all to avoid lazy load

    # Count active tokens before
    before = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked == False
        )
    )
    active_before = len(before.scalars().all())
    assert active_before > 0

    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": verified_user["password"],
                "new_password": "ChangedPass123!",
            },
            headers=auth_headers,
        )

    # All old tokens should be revoked (except the new one from change-password)
    db_session.expire_all()
    after = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked == False
        )
    )
    active_after = len(after.scalars().all())
    # Should have exactly 1 new active token (the one from change-password)
    assert active_after == 1


# =====================================================================
# Session Tests (4)
# =====================================================================


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, auth_headers: dict):
    """Authenticated user can list sessions."""
    resp = await client.get("/api/v1/auth/sessions", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_revoke_session(
    client: AsyncClient, verified_user: dict, auth_headers: dict, login_with_2fa
):
    """User can revoke a specific session."""
    # Create a second session by logging in again (handles 2FA)
    await login_with_2fa(client, verified_user["email"], verified_user["password"])

    # List sessions
    sessions_resp = await client.get("/api/v1/auth/sessions", headers=auth_headers)
    sessions = sessions_resp.json()
    assert len(sessions) >= 1

    # Revoke the first session
    session_id = sessions[0]["id"]
    revoke_resp = await client.delete(
        f"/api/v1/auth/sessions/{session_id}",
        headers=auth_headers,
    )
    assert revoke_resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_all(client: AsyncClient, auth_headers: dict):
    """User can revoke all sessions."""
    resp = await client.post("/api/v1/auth/logout-all", headers=auth_headers)
    assert resp.status_code == 200
    assert "sessie" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_session_is_current(client: AsyncClient, verified_user: dict, login_with_2fa):
    """Sessions endpoint marks the current session with is_current=True."""
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    current_sessions = [s for s in sessions if s["is_current"]]
    assert len(current_sessions) == 1


@pytest.mark.asyncio
async def test_revoke_other_user_session(
    client: AsyncClient, auth_headers: dict
):
    """User cannot revoke another user's session (returns 404)."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/api/v1/auth/sessions/{fake_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# =====================================================================
# 2FA Tests (7)
# =====================================================================


@pytest_asyncio.fixture
async def two_fa_user(client: AsyncClient, db_session: AsyncSession) -> dict:
    """A regular (non-superadmin) verified user for 2FA lifecycle tests."""
    user_data = {
        "email": f"2fa-{uuid.uuid4().hex[:8]}@example.com",
        "password": "TwoFATestPass123!",
        "full_name": "2FA Test User",
    }
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201

    await db_session.execute(
        update(User).where(User.id == uuid.UUID(response.json()["id"])).values(
            email_verified=True
        )
    )
    await db_session.flush()
    return user_data


@pytest_asyncio.fixture
async def two_fa_headers(client: AsyncClient, two_fa_user: dict) -> dict:
    """Auth headers for the 2FA test user (non-superadmin, direct login)."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": two_fa_user["email"], "password": two_fa_user["password"]},
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_2fa_setup(client: AsyncClient, two_fa_headers: dict):
    """User can start 2FA setup."""
    resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "secret" in data
    assert "qr_code_uri" in data


@pytest.mark.asyncio
async def test_2fa_verify_setup(client: AsyncClient, two_fa_headers: dict):
    """User can verify 2FA setup with correct TOTP code."""
    import pyotp

    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)

    resp = await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "backup_codes" in data
    assert len(data["backup_codes"]) > 0


@pytest.mark.asyncio
async def test_2fa_verify_setup_wrong_code(client: AsyncClient, two_fa_headers: dict):
    """Wrong TOTP code during setup fails."""
    await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    resp = await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": "000000"},
        headers=two_fa_headers,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_2fa_login_flow(
    client: AsyncClient, two_fa_user: dict, two_fa_headers: dict
):
    """Full 2FA login flow: setup → enable → login requires code."""
    import pyotp

    # Setup 2FA
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)

    # Verify setup
    resp = await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )
    assert resp.status_code == 200

    # Login should now require 2FA
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": two_fa_user["email"], "password": two_fa_user["password"]},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["requires_2fa"] is True
    assert data["two_factor_token"] is not None
    assert data["access_token"] is None

    # Verify 2FA
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_token": data["two_factor_token"],
            "code": totp.now(),
        },
    )
    assert verify_resp.status_code == 200
    tokens = verify_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_2fa_wrong_totp_code(
    client: AsyncClient, two_fa_user: dict, two_fa_headers: dict
):
    """Wrong TOTP code during login fails."""
    import pyotp

    # Setup and enable 2FA
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": two_fa_user["email"], "password": two_fa_user["password"]},
    )
    two_factor_token = login_resp.json()["two_factor_token"]

    # Wrong code
    resp = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"two_factor_token": two_factor_token, "code": "999999"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_2fa_backup_code(
    client: AsyncClient, two_fa_user: dict, two_fa_headers: dict
):
    """Backup code works for 2FA login."""
    import pyotp

    # Setup and enable 2FA
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )
    backup_codes = verify_resp.json()["backup_codes"]
    assert len(backup_codes) > 0

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": two_fa_user["email"], "password": two_fa_user["password"]},
    )
    two_factor_token = login_resp.json()["two_factor_token"]

    # Use backup code
    resp = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"two_factor_token": two_factor_token, "code": backup_codes[0]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_2fa_disable(
    client: AsyncClient, two_fa_user: dict, two_fa_headers: dict
):
    """User can disable 2FA with password."""
    import pyotp

    # Setup and enable
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )

    # Disable
    resp = await client.post(
        "/api/v1/auth/2fa/disable",
        json={"password": two_fa_user["password"]},
        headers=two_fa_headers,
    )
    assert resp.status_code == 200

    # Login should no longer require 2FA (non-superadmin user)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": two_fa_user["email"], "password": two_fa_user["password"]},
    )
    data = login_resp.json()
    assert data.get("requires_2fa") is False or data.get("access_token") is not None


@pytest.mark.asyncio
async def test_2fa_regenerate_backup_codes(
    client: AsyncClient, two_fa_user: dict, two_fa_headers: dict
):
    """User can regenerate backup codes after 2FA is enabled."""
    import pyotp

    # Setup and enable 2FA
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )
    old_codes = verify_resp.json()["backup_codes"]

    # Regenerate backup codes
    regen_resp = await client.post(
        "/api/v1/auth/2fa/regenerate-backup-codes",
        json={"password": two_fa_user["password"]},
        headers=two_fa_headers,
    )
    assert regen_resp.status_code == 200
    new_codes = regen_resp.json()["backup_codes"]
    assert len(new_codes) > 0
    assert new_codes != old_codes  # New codes should be different


@pytest.mark.asyncio
async def test_2fa_regenerate_backup_codes_wrong_password(
    client: AsyncClient, two_fa_headers: dict
):
    """Regenerate with wrong password fails."""
    import pyotp

    # Setup and enable 2FA
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=two_fa_headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/2fa/verify-setup",
        json={"code": totp.now()},
        headers=two_fa_headers,
    )

    # Try regenerate with wrong password
    resp = await client.post(
        "/api/v1/auth/2fa/regenerate-backup-codes",
        json={"password": "WrongPassword!"},
        headers=two_fa_headers,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_2fa_setup_already_enabled(client: AsyncClient, auth_headers: dict):
    """Cannot setup 2FA when it is already enabled (must disable first).

    Uses the superadmin verified_user which has 2FA pre-enabled via conftest.
    """
    resp = await client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
    assert resp.status_code == 409
    assert "al actief" in resp.json()["detail"].lower()


# =====================================================================
# Audit Tests (2)
# =====================================================================


@pytest.mark.asyncio
async def test_audit_login_entry(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict, login_with_2fa
):
    """Login creates an audit log entry (via password change which has audit)."""
    tokens = await login_with_2fa(client, verified_user["email"], verified_user["password"])
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": verified_user["password"],
                "new_password": "AuditTestPass123!",
            },
            headers=headers,
        )

    # Check audit logs
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.password_changed")
    )
    logs = result.scalars().all()
    assert len(logs) >= 1


@pytest.mark.asyncio
async def test_audit_password_reset_entry(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Password reset request creates an audit entry."""
    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": verified_user["email"]},
        )

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.password_reset_requested")
    )
    logs = result.scalars().all()
    assert len(logs) >= 1


# =====================================================================
# Bulk Invite & Invitation History Tests
# =====================================================================


@pytest.mark.asyncio
async def test_bulk_invite(client: AsyncClient, auth_headers: dict, test_tenant):
    """Bulk invite creates multiple invitations."""
    tenant_id = str(test_tenant["tenant"].id)
    emails = ["bulk1@example.com", "bulk2@example.com", "bulk3@example.com"]
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations/bulk",
            json={"emails": emails},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3
    assert all(r["success"] for r in data["results"])


@pytest.mark.asyncio
async def test_bulk_invite_partial_failure(client: AsyncClient, auth_headers: dict, test_tenant):
    """Bulk invite continues on individual failures (duplicate email)."""
    tenant_id = str(test_tenant["tenant"].id)
    # Create one invitation first
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "existing-bulk@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    # Now bulk with duplicate and new
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations/bulk",
            json={"emails": ["existing-bulk@example.com", "new-bulk@example.com"]},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["failed"] == 1


@pytest.mark.asyncio
async def test_list_invitations_with_status_filter(
    client: AsyncClient, auth_headers: dict, test_tenant, db_session: AsyncSession
):
    """List invitations supports status filter."""
    tenant_id = str(test_tenant["tenant"].id)
    # Create an invitation
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "filter-test@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    assert resp.status_code == 201

    # List pending - should find it
    resp = await client.get(
        f"/api/v1/schools/{tenant_id}/invitations?status=pending",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    pending = resp.json()
    assert any(i["email"] == "filter-test@example.com" for i in pending)
    assert all(i["status"] == "pending" for i in pending)

    # List accepted - should not find it
    resp = await client.get(
        f"/api/v1/schools/{tenant_id}/invitations?status=accepted",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    accepted = resp.json()
    assert not any(i["email"] == "filter-test@example.com" for i in accepted)


@pytest.mark.asyncio
async def test_list_invitations_revoked_status(
    client: AsyncClient, auth_headers: dict, test_tenant
):
    """Revoked invitations appear in revoked status filter."""
    tenant_id = str(test_tenant["tenant"].id)
    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/schools/{tenant_id}/invitations",
            json={"email": "revoke-filter@example.com", "role": "teacher"},
            headers=auth_headers,
        )
    inv_id = resp.json()["id"]

    # Revoke it
    await client.delete(
        f"/api/v1/schools/{tenant_id}/invitations/{inv_id}",
        headers=auth_headers,
    )

    # Should appear in revoked filter
    resp = await client.get(
        f"/api/v1/schools/{tenant_id}/invitations?status=revoked",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    revoked = resp.json()
    assert any(i["email"] == "revoke-filter@example.com" for i in revoked)
