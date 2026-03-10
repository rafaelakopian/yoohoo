"""Invitation & Token Hardening Security Tests.

Tests for HMAC token migration, transaction atomicity,
audit logging, and input validation.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import hmac_hash
from app.modules.platform.auth.models import (
    AuditLog,
    Invitation,
    PasswordResetToken,
    RefreshToken,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.permissions_setup import create_default_groups
from app.modules.platform.tenant_mgmt.models import Tenant


# ======================================================================
# Fixtures
# ======================================================================


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession, verified_user: dict, client: AsyncClient, auth_headers: dict):
    """Create a test tenant and membership for verified_user as org_admin."""
    slug = f"sec-test-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name="Security Test School", slug=slug, is_active=True)
    db_session.add(tenant)
    await db_session.flush()

    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    user = result.scalar_one()

    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant.id
    )
    db_session.add(membership)
    await db_session.flush()

    # Create default groups and assign user to beheerder (all permissions)
    groups = await create_default_groups(db_session, tenant.id)
    db_session.add(UserGroupAssignment(user_id=user.id, group_id=groups["beheerder"].id))
    await db_session.flush()

    return {"tenant": tenant, "slug": slug, "user": user}


# ======================================================================
# HMAC Token Migration -- Invitation
# ======================================================================


@pytest.mark.asyncio
async def test_invitation_token_uses_hmac(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """New invitation tokens should use HMAC-SHA256, not plain SHA256."""
    slug = test_tenant["slug"]
    email = f"hmac-test-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    assert len(invitation.token_hash) == 64

@pytest.mark.asyncio
async def test_invite_info_legacy_token_works(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Invitation with legacy SHA256 hash should still be found via invite-info."""
    slug = test_tenant["slug"]
    email = f"legacy-info-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )

    raw_token = secrets.token_urlsafe(32)
    legacy_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    invitation.token_hash = legacy_hash
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invite-info?token={raw_token}")
    assert resp.status_code == 200
    assert resp.json()["email"] == email


@pytest.mark.asyncio
async def test_invite_info_legacy_auto_migrates(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """After accessing a legacy-hashed invitation, the hash should be auto-migrated to HMAC."""
    slug = test_tenant["slug"]
    email = f"migrate-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )

    raw_token = secrets.token_urlsafe(32)
    legacy_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    invitation.token_hash = legacy_hash
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invite-info?token={raw_token}")
    assert resp.status_code == 200

    await db_session.refresh(invitation)
    expected_hmac = hmac_hash(raw_token)
    assert invitation.token_hash == expected_hmac
    assert invitation.token_hash != legacy_hash


@pytest.mark.asyncio
async def test_accept_legacy_token_works(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Accepting an invitation with a legacy SHA256 hash should succeed."""
    slug = test_tenant["slug"]
    email = f"accept-legacy-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )

    raw_token = secrets.token_urlsafe(32)
    legacy_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    invitation.token_hash = legacy_hash
    await db_session.flush()

    resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "Legacy User",
    })
    assert resp.status_code == 200
    assert resp.json()["is_new_user"] is True

# ======================================================================
# Transaction Atomicity
# ======================================================================


@pytest.mark.asyncio
async def test_accept_replay_rejected(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Replaying an already-accepted invitation token must be rejected."""
    slug = test_tenant["slug"]
    email = f"replay-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )

    raw_token = secrets.token_urlsafe(32)
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    invitation.token_hash = hmac_hash(raw_token)
    await db_session.flush()

    resp1 = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "Replay User",
    })
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "Replay User 2",
    })
    assert resp2.status_code == 401


# ======================================================================
# Token min_length Validation
# ======================================================================


@pytest.mark.asyncio
async def test_invite_info_short_token_422(client: AsyncClient):
    """invite-info with a token shorter than 20 chars must return 422."""
    resp = await client.get("/api/v1/auth/invite-info?token=shorttoken")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_accept_short_token_422(client: AsyncClient):
    """accept-invite with a token shorter than 20 chars must return 422."""
    resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": "short",
        "password": "SecurePass123!",
        "full_name": "Test",
    })
    assert resp.status_code == 422


# ======================================================================
# Audit Logging
# ======================================================================


@pytest.mark.asyncio
async def test_invite_info_audit_log_created(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_tenant
):
    """Calling invite-info should create an audit log entry."""
    slug = test_tenant["slug"]
    email = f"audit-{uuid.uuid4().hex[:8]}@example.com"

    with patch("app.modules.platform.auth.invitation.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post(
            f"/api/v1/org/{slug}/access/invitations",
            json={"email": email, "role": "parent"},
            headers=auth_headers,
        )

    raw_token = secrets.token_urlsafe(32)
    result = await db_session.execute(
        select(Invitation).where(Invitation.email == email)
    )
    invitation = result.scalar_one()
    invitation.token_hash = hmac_hash(raw_token)
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invite-info?token={raw_token}")
    assert resp.status_code == 200

    logs = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "invitation.info_viewed")
    )
    log_entries = logs.scalars().all()
    matching = [l for l in log_entries if l.details and l.details.get("email") == email]
    assert len(matching) >= 1

# ======================================================================
# HMAC Token Migration -- Password Reset
# ======================================================================


@pytest.mark.asyncio
async def test_password_reset_uses_hmac(
    client: AsyncClient, db_session: AsyncSession
):
    """New password reset tokens should use HMAC-SHA256."""
    email = f"pwreset-{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "TestPass123!", "full_name": "PW Test",
        })
    user_result = await db_session.execute(select(User).where(User.email == email))
    user = user_result.scalar_one()
    user.email_verified = True
    await db_session.flush()

    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        await client.post("/api/v1/auth/forgot-password", json={"email": email})

    token_result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    token_record = token_result.scalar_one()
    assert len(token_record.token_hash) == 64


@pytest.mark.asyncio
async def test_password_reset_legacy_lookup(
    client: AsyncClient, db_session: AsyncSession
):
    """Password reset with legacy SHA256 hash should still work."""
    email = f"pwlegacy-{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "TestPass123!", "full_name": "Legacy PW",
        })
    user_result = await db_session.execute(select(User).where(User.email == email))
    user = user_result.scalar_one()
    user.email_verified = True
    await db_session.flush()

    raw_token = secrets.token_urlsafe(32)
    legacy_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_record = PasswordResetToken(
        user_id=user.id,
        token_hash=legacy_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db_session.add(token_record)
    await db_session.flush()

    resp = await client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewSecurePass123!",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_refresh_uses_hmac(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, verified_user
):
    """After change-password, the new refresh token should be stored with HMAC hash."""
    with patch("app.modules.platform.auth.password.service.send_email_safe", new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "TestPassword123!",
                "new_password": "NewSecurePass456!",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    new_refresh = data["refresh_token"]

    expected_hash = hmac_hash(new_refresh)
    token_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == expected_hash,
            RefreshToken.revoked.is_(False),
        )
    )
    token_record = token_result.scalar_one_or_none()
    assert token_record is not None, "Refresh token not found with HMAC hash"
