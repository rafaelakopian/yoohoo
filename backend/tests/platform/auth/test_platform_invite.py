"""Platform-level invitation tests.

Tests for creating, accepting, and validating platform invitations
(tenant_id=NULL, invitation_type="platform").
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import hmac_hash
from app.modules.platform.auth.models import (
    GroupPermission,
    Invitation,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)

MOCK_SEND_EMAIL = "app.modules.platform.auth.invitation.service.send_email_safe"
MOCK_SEND_EMAIL_REGISTER = "app.modules.platform.auth.core.service.send_email"

# Fixed TOTP secret (matches conftest.py)
TEST_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


# ======================================================================
# Helpers
# ======================================================================


async def _create_regular_user(
    client: AsyncClient, db_session: AsyncSession, email: str | None = None
) -> User:
    """Register a non-superadmin, verified user (no platform group assignments)."""
    email = email or f"regular-{uuid.uuid4().hex[:8]}@example.com"
    with patch(MOCK_SEND_EMAIL_REGISTER, new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "TestPassword123!",
            "full_name": "Regular User",
        })
    assert resp.status_code == 201

    from sqlalchemy import update
    await db_session.execute(
        update(User).where(User.email == email).values(email_verified=True)
    )
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def _get_auth_headers_for_user(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> dict:
    """Get auth headers for a non-2FA user by logging in."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": user.email,
        "password": "TestPassword123!",
    })
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


async def _create_platform_invite_directly(
    db_session: AsyncSession, email: str, inviter_id: uuid.UUID,
    expired: bool = False, accepted: bool = False, revoked: bool = False,
    group_id: uuid.UUID | None = None,
) -> tuple[Invitation, str]:
    """Create an invitation record directly in DB (bypasses service logic)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hmac_hash(raw_token)
    now = datetime.now(timezone.utc)

    if expired:
        expires_at = now - timedelta(hours=1)
    else:
        expires_at = now + timedelta(hours=72)

    invitation = Invitation(
        tenant_id=None,
        email=email,
        group_id=group_id,
        token_hash=token_hash,
        expires_at=expires_at,
        invited_by_id=inviter_id,
        invitation_type="platform",
        accepted_at=now if accepted else None,
        revoked=revoked,
    )
    db_session.add(invitation)
    await db_session.flush()
    return invitation, raw_token


# ======================================================================
# 1. Create invite — new email
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_new_email(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Inviting an unknown email should succeed and create an Invitation record."""
    email = f"new-platform-{uuid.uuid4().hex[:8]}@example.com"

    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": email},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Uitnodiging is verstuurd"

    # Verify invitation record
    result = await db_session.execute(
        select(Invitation).where(
            Invitation.email == email,
            Invitation.tenant_id.is_(None),
            Invitation.invitation_type == "platform",
        )
    )
    invitation = result.scalar_one()
    assert invitation.group_id is not None
    assert invitation.accepted_at is None
    assert invitation.revoked is False


# ======================================================================
# 2. Create invite — existing user, not a platform member
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_existing_user_not_platform(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Inviting an existing user who is NOT a platform member should succeed."""
    regular_user = await _create_regular_user(client, db_session)

    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": regular_user.email},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Uitnodiging is verstuurd"


# ======================================================================
# 3. Create invite — already a platform member (409)
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_already_platform_member(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, verified_user: dict
):
    """Inviting a user who is already a platform member should return 409."""
    # verified_user is superadmin = platform member
    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": verified_user["email"]},
            headers=auth_headers,
        )

    assert resp.status_code == 409
    assert "Al een platformgebruiker" in resp.json()["detail"]


# ======================================================================
# 4. Create invite — duplicate pending (409)
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_duplicate_pending(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """A second invite for the same email (while first is still pending) should return 409."""
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp1 = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": email},
            headers=auth_headers,
        )
    assert resp1.status_code == 200

    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp2 = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": email},
            headers=auth_headers,
        )
    assert resp2.status_code == 409
    assert "al een uitnodiging open" in resp2.json()["detail"]


# ======================================================================
# 5. Create invite — after expired invite is OK
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_after_expired_ok(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, verified_user: dict
):
    """Re-inviting after a previous invite has expired should succeed."""
    email = f"expired-{uuid.uuid4().hex[:8]}@example.com"

    # Get inviter user ID
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    # Create expired invite directly in DB
    await _create_platform_invite_directly(
        db_session, email, inviter.id, expired=True
    )

    # New invite should succeed
    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": email},
            headers=auth_headers,
        )

    assert resp.status_code == 200


# ======================================================================
# 6. Create invite — non-superadmin gets 403
# ======================================================================


@pytest.mark.asyncio
async def test_create_invite_non_superadmin_403(
    client: AsyncClient, db_session: AsyncSession
):
    """A non-superadmin user should get 403 when trying to invite."""
    regular_user = await _create_regular_user(client, db_session)
    headers = await _get_auth_headers_for_user(client, db_session, regular_user)

    resp = await client.post(
        "/api/v1/platform/access/users/invite",
        json={"email": "someone@example.com"},
        headers=headers,
    )

    assert resp.status_code == 403


# ======================================================================
# 7. Accept — new user creates account
# ======================================================================


@pytest.mark.asyncio
async def test_accept_new_user_creates_account(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, verified_user: dict
):
    """A new user accepting a platform invite should get an account + Nieuw group."""
    email = f"newaccept-{uuid.uuid4().hex[:8]}@example.com"

    # Get inviter
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    # Create invitation directly
    invitation, raw_token = await _create_platform_invite_directly(
        db_session, email, inviter.id
    )
    # Ensure group exists
    nieuw_group = PermissionGroup(
        tenant_id=None, name="Nieuw", slug="nieuw",
        description="Landing-groep", is_default=True,
    )
    db_session.add(nieuw_group)
    await db_session.flush()
    invitation.group_id = nieuw_group.id
    await db_session.flush()

    # Accept as new user
    resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "Nieuwe Medewerker",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_new_user"] is True
    assert data["tenant_name"] is None

    # Verify user was created
    user_result = await db_session.execute(
        select(User).where(User.email == email)
    )
    new_user = user_result.scalar_one()
    assert new_user.full_name == "Nieuwe Medewerker"
    assert new_user.email_verified is True

    # Verify group assignment
    assignment_result = await db_session.execute(
        select(UserGroupAssignment).where(
            UserGroupAssignment.user_id == new_user.id,
            UserGroupAssignment.group_id == nieuw_group.id,
        )
    )
    assert assignment_result.scalar_one_or_none() is not None


# ======================================================================
# 8. Accept — existing user adds group (requires auth)
# ======================================================================


@pytest.mark.asyncio
async def test_accept_existing_user_adds_group(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """An existing user accepting a platform invite must be logged in; group is assigned."""
    # Create a regular (non-platform) user
    regular_user = await _create_regular_user(client, db_session)
    headers = await _get_auth_headers_for_user(client, db_session, regular_user)

    # Get inviter
    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    # Ensure nieuw group
    nieuw_result = await db_session.execute(
        select(PermissionGroup).where(
            PermissionGroup.tenant_id.is_(None),
            PermissionGroup.slug == "nieuw",
        )
    )
    nieuw_group = nieuw_result.scalar_one_or_none()
    if not nieuw_group:
        nieuw_group = PermissionGroup(
            tenant_id=None, name="Nieuw", slug="nieuw",
            description="Landing-groep", is_default=True,
        )
        db_session.add(nieuw_group)
        await db_session.flush()

    # Create invitation for regular user
    invitation, raw_token = await _create_platform_invite_directly(
        db_session, regular_user.email, inviter.id, group_id=nieuw_group.id
    )

    # Accept WITH auth headers (logged in as the invited user)
    resp = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_new_user"] is False

    # Verify group assignment
    assignment_result = await db_session.execute(
        select(UserGroupAssignment).where(
            UserGroupAssignment.user_id == regular_user.id,
            UserGroupAssignment.group_id == nieuw_group.id,
        )
    )
    assert assignment_result.scalar_one_or_none() is not None


# ======================================================================
# 9. Accept — no TenantMembership for platform invite
# ======================================================================


@pytest.mark.asyncio
async def test_accept_no_tenant_membership(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Accepting a platform invite must NOT create a TenantMembership."""
    email = f"no-tenant-{uuid.uuid4().hex[:8]}@example.com"

    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    invitation, raw_token = await _create_platform_invite_directly(
        db_session, email, inviter.id
    )

    resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "No Tenant User",
    })
    assert resp.status_code == 200

    # Verify NO TenantMembership
    user_result = await db_session.execute(
        select(User).where(User.email == email)
    )
    new_user = user_result.scalar_one()

    membership_result = await db_session.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == new_user.id,
        )
    )
    assert membership_result.scalar_one_or_none() is None


# ======================================================================
# 10. Accept — expired token
# ======================================================================


@pytest.mark.asyncio
async def test_accept_expired_token(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Accepting an expired platform invite should fail."""
    email = f"expired-accept-{uuid.uuid4().hex[:8]}@example.com"

    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    _, raw_token = await _create_platform_invite_directly(
        db_session, email, inviter.id, expired=True
    )

    resp = await client.post("/api/v1/auth/accept-invite", json={
        "token": raw_token,
        "password": "SecurePass123!",
        "full_name": "Expired User",
    })
    assert resp.status_code == 401


# ======================================================================
# 11. Accept — replay blocked
# ======================================================================


@pytest.mark.asyncio
async def test_accept_replay_blocked(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """Accepting the same platform invite token twice should fail on second attempt."""
    email = f"replay-{uuid.uuid4().hex[:8]}@example.com"

    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    _, raw_token = await _create_platform_invite_directly(
        db_session, email, inviter.id
    )

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
# 12. Invite info — no org_name for platform invite
# ======================================================================


@pytest.mark.asyncio
async def test_invite_info_no_org_name(
    client: AsyncClient, db_session: AsyncSession, verified_user: dict
):
    """InviteInfo for a platform invite should return org_name=None."""
    email = f"info-{uuid.uuid4().hex[:8]}@example.com"

    result = await db_session.execute(
        select(User).where(User.email == verified_user["email"])
    )
    inviter = result.scalar_one()

    _, raw_token = await _create_platform_invite_directly(
        db_session, email, inviter.id
    )

    resp = await client.get(f"/api/v1/auth/invite-info?token={raw_token}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["org_name"] is None
    assert data["email"] == email
    assert data["invitation_type"] == "platform"
    assert data["is_existing_user"] is False


# ======================================================================
# 13. Nieuw group — on-demand creation with zero permissions
# ======================================================================


@pytest.mark.asyncio
async def test_nieuw_group_on_demand_zero_permissions(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """The 'Nieuw' group should be created on-demand with exactly 0 permissions."""
    # Delete any existing "nieuw" group to test on-demand creation
    existing = await db_session.execute(
        select(PermissionGroup).where(
            PermissionGroup.tenant_id.is_(None),
            PermissionGroup.slug == "nieuw",
        )
    )
    existing_group = existing.scalar_one_or_none()
    if existing_group:
        # Clean up assignments and the group
        await db_session.execute(
            select(UserGroupAssignment).where(
                UserGroupAssignment.group_id == existing_group.id
            )
        )
        # Delete assignments
        from sqlalchemy import delete
        await db_session.execute(
            delete(UserGroupAssignment).where(
                UserGroupAssignment.group_id == existing_group.id
            )
        )
        await db_session.execute(
            delete(GroupPermission).where(
                GroupPermission.group_id == existing_group.id
            )
        )
        await db_session.execute(
            delete(Invitation).where(
                Invitation.group_id == existing_group.id
            )
        )
        await db_session.delete(existing_group)
        await db_session.flush()

    # Trigger creation via invite
    email = f"nieuw-group-{uuid.uuid4().hex[:8]}@example.com"
    with patch(MOCK_SEND_EMAIL, new_callable=AsyncMock, return_value=True):
        resp = await client.post(
            "/api/v1/platform/access/users/invite",
            json={"email": email},
            headers=auth_headers,
        )
    assert resp.status_code == 200

    # Verify the group was created
    result = await db_session.execute(
        select(PermissionGroup).where(
            PermissionGroup.tenant_id.is_(None),
            PermissionGroup.slug == "nieuw",
        )
    )
    nieuw_group = result.scalar_one()
    assert nieuw_group.name == "Nieuw"
    assert nieuw_group.is_default is True

    # Verify zero permissions
    perm_result = await db_session.execute(
        select(GroupPermission).where(
            GroupPermission.group_id == nieuw_group.id
        )
    )
    permissions = perm_result.scalars().all()
    assert len(permissions) == 0
