"""Tests for account archive, reactivation, and anonymization."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import (
    TenantMembership,
    User,
    UserGroupAssignment,
)


@pytest_asyncio.fixture
async def archived_user(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a verified user and archive them via the delete-account endpoint."""
    email = f"archive-{uuid.uuid4().hex[:8]}@example.com"
    password = "ArchiveTest123!"

    # Register
    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": "Archive Test User",
        })
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["id"])

    # Verify email directly in DB (non-superadmin, no TOTP needed)
    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    # Login
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Delete (archive) account
    del_resp = await client.post(
        "/api/v1/auth/delete-account",
        json={"password": password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200

    return {"id": user_id, "email": email, "password": password}


# --- Archive behavior tests ---


@pytest.mark.asyncio
async def test_archive_sets_fields(
    client: AsyncClient, archived_user: dict, db_session: AsyncSession,
):
    """Archiving sets archived_at, archived_by, and is_active=False."""
    result = await db_session.execute(
        select(User).where(User.id == archived_user["id"])
    )
    user = result.scalar_one()

    assert user.is_active is False
    assert user.archived_at is not None
    assert user.archived_by == str(archived_user["id"])
    assert user.anonymized_at is None


@pytest.mark.asyncio
async def test_archive_preserves_pii(
    client: AsyncClient, archived_user: dict, db_session: AsyncSession,
):
    """Archiving preserves email and full_name (no immediate anonymization)."""
    result = await db_session.execute(
        select(User).where(User.id == archived_user["id"])
    )
    user = result.scalar_one()

    assert user.email == archived_user["email"]
    assert user.full_name == "Archive Test User"
    assert user.hashed_password != "ANONYMIZED"


@pytest.mark.asyncio
async def test_archive_deactivates_memberships(
    client: AsyncClient, db_session: AsyncSession,
):
    """Archiving deactivates memberships instead of deleting them."""
    email = f"member-{uuid.uuid4().hex[:8]}@example.com"
    password = "MemberTest123!"

    with patch("app.modules.platform.auth.core.service.send_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": "Member Test",
        })
    user_id = uuid.UUID(resp.json()["id"])

    await db_session.execute(
        update(User).where(User.id == user_id).values(email_verified=True)
    )
    await db_session.flush()

    # Create a tenant membership
    from app.modules.platform.tenant_mgmt.models import Tenant
    tenant_id = uuid.uuid4()
    result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
    if not result.scalar_one_or_none():
        db_session.add(Tenant(
            id=tenant_id, name="Archive Test Org", slug=f"archive-{uuid.uuid4().hex[:6]}",
            is_active=True, is_provisioned=True,
        ))
        await db_session.flush()

    membership = TenantMembership(
        user_id=user_id, tenant_id=tenant_id, is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    # Login and archive
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    token = login_resp.json()["access_token"]

    await client.post(
        "/api/v1/auth/delete-account",
        json={"password": password},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Membership should still exist but be deactivated
    result = await db_session.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    )
    m = result.scalar_one()
    assert m is not None
    assert m.is_active is False


@pytest.mark.asyncio
async def test_archived_user_cannot_login(
    client: AsyncClient, archived_user: dict,
):
    """Archived user cannot login."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": archived_user["email"],
        "password": archived_user["password"],
    })
    assert resp.status_code == 401


# --- Reactivation tests ---


@pytest.mark.asyncio
async def test_reactivate_archived_account(
    client: AsyncClient, archived_user: dict, auth_headers: dict, db_session: AsyncSession,
):
    """Superadmin can reactivate an archived account."""
    resp = await client.post(
        f"/api/v1/platform/access/users/{archived_user['id']}/reactivate",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert data["email"] == archived_user["email"]

    # Verify DB state
    result = await db_session.execute(
        select(User).where(User.id == archived_user["id"])
    )
    user = result.scalar_one()
    assert user.archived_at is None
    assert user.archived_by is None
    assert user.is_active is True


@pytest.mark.asyncio
async def test_reactivate_fails_when_disabled(
    client: AsyncClient, archived_user: dict, auth_headers: dict,
):
    """Reactivation fails when data_retention_allow_reactivation is False."""
    with patch("app.modules.platform.admin.service.settings") as mock_settings:
        mock_settings.data_retention_allow_reactivation = False
        resp = await client.post(
            f"/api/v1/platform/access/users/{archived_user['id']}/reactivate",
            headers=auth_headers,
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_fails_for_anonymized(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot reactivate an anonymized account."""
    # Create an anonymized user directly in DB
    user = User(
        email=f"anon-{uuid.uuid4().hex[:8]}@deleted.local",
        hashed_password="ANONYMIZED",
        full_name="Geanonimiseerd",
        is_active=False,
        archived_at=datetime.now(timezone.utc) - timedelta(days=600),
        anonymized_at=datetime.now(timezone.utc),
        archived_by="system",
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/platform/access/users/{user.id}/reactivate",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "geanonimiseerd" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reactivate_fails_for_non_archived(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot reactivate an account that is not archived."""
    # Create a normal active user
    user = User(
        email=f"active-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="SomeHash",
        full_name="Active User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/platform/access/users/{user.id}/reactivate",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "niet gearchiveerd" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reactivate_fails_window_expired(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Cannot reactivate when reactivation window has expired."""
    user = User(
        email=f"expired-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="SomeHash",
        full_name="Expired Archive User",
        is_active=False,
        archived_at=datetime.now(timezone.utc) - timedelta(days=9999),
        archived_by="self",
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/platform/access/users/{user.id}/reactivate",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "verlopen" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reactivate_requires_permission(client: AsyncClient):
    """Unauthenticated request to reactivate fails."""
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/platform/access/users/{fake_id}/reactivate")
    assert resp.status_code == 401


# --- Anonymization cron job tests ---


@pytest.mark.asyncio
async def test_anonymize_job_processes_expired_accounts(db_session: AsyncSession):
    """Anonymize job anonymizes accounts past the retention window."""
    from app.core.jobs.maintenance import anonymize_archived_accounts_job

    # Create an archived user past the retention window
    user = User(
        email=f"old-archive-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="SomeHash",
        full_name="Old Archive User",
        is_active=False,
        archived_at=datetime.now(timezone.utc) - timedelta(days=9999),
        archived_by="self",
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id

    # Run the job with a session factory that returns our test session
    class FakeFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            pass

    ctx = {"central_session_factory": FakeFactory()}

    with patch("app.core.jobs.maintenance.settings") as mock_settings:
        mock_settings.data_retention_auto_anonymize = True
        mock_settings.data_retention_account_archive_days = 548
        result = await anonymize_archived_accounts_job(ctx)

    assert result is True

    # Verify the user was anonymized
    result = await db_session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    assert user.anonymized_at is not None
    assert user.full_name == "Geanonimiseerd"
    assert user.hashed_password == "ANONYMIZED"
    assert "deleted.local" in user.email


@pytest.mark.asyncio
async def test_anonymize_job_skips_when_disabled():
    """Anonymize job does nothing when auto_anonymize is disabled."""
    from app.core.jobs.maintenance import anonymize_archived_accounts_job

    with patch("app.core.jobs.maintenance.settings") as mock_settings:
        mock_settings.data_retention_auto_anonymize = False
        result = await anonymize_archived_accounts_job({})

    assert result is True
