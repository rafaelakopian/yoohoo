"""Tests for Fase H-1: Platform → Tenant Notification Kanaal.

15 tests covering:
1. Notification type registry
2. Create notification (admin)
3. Create notification (missing type → 404)
4. List notifications (admin)
5. Update draft notification
6. Update published notification → 409
7. Delete draft notification
8. Delete published notification → 409
9. Publish notification (fan-out)
10. User inbox (after publish)
11. Mark notification as read
12. Mark all notifications as read
13. Unread count
14. Get tenant preferences (defaults)
15. Update tenant preference
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.models import (
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.notifications.models import (
    PlatformNotification,
    PlatformNotificationRecipient,
)
from tests.conftest import TEST_TENANT_UUID


@pytest.fixture
def notification_data() -> dict:
    return {
        "notification_type": "platform_announcement",
        "title": "Test melding",
        "message": "Dit is een testmelding voor alle organisaties.",
        "severity": "info",
        "target_scope": "all",
    }


async def _ensure_tenant_with_owner(db_session: AsyncSession, verified_user: dict):
    """Ensure test tenant exists with the test user as owner (needed for fan-out)."""
    from app.modules.platform.tenant_mgmt.models import Tenant

    # Look up user ID
    result = await db_session.execute(
        select(User.id).where(User.email == verified_user["email"])
    )
    user_id = result.scalar_one()

    result = await db_session.execute(select(Tenant).where(Tenant.id == TEST_TENANT_UUID))
    existing = result.scalar_one_or_none()
    if existing:
        # Update owner to current test user (may differ between tests due to commits)
        existing.owner_id = user_id
        await db_session.flush()
        return

    tenant = Tenant(
        id=TEST_TENANT_UUID, name="Test Tenant", slug="test",
        is_active=True, is_provisioned=True, owner_id=user_id,
    )
    db_session.add(tenant)
    await db_session.flush()


# ---------------------------------------------------------------------------
# 1. Notification type registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notification_types(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/platform/notifications/types",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    codes = [t["code"] for t in data]
    assert "maintenance" in codes
    assert "platform_announcement" in codes
    assert "security_alert" in codes


# ---------------------------------------------------------------------------
# 2. Create notification (admin)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_notification(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
):
    response = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test melding"
    assert data["is_published"] is False
    assert data["notification_type"] == "platform_announcement"
    assert data["severity"] == "info"


# ---------------------------------------------------------------------------
# 3. Create notification with unknown type → error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_notification_unknown_type(
    client: AsyncClient, auth_headers: dict,
):
    response = await client.post(
        "/api/v1/platform/notifications",
        json={
            "notification_type": "nonexistent_type",
            "title": "Bad",
            "message": "Bad type",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 4. List notifications (admin)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notifications(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
):
    # Create one
    await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )

    response = await client.get(
        "/api/v1/platform/notifications",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


# ---------------------------------------------------------------------------
# 5. Update draft notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_draft_notification(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
):
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/platform/notifications/{notif_id}",
        json={"title": "Updated titel"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated titel"


# ---------------------------------------------------------------------------
# 6. Update published notification → 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_published_notification_fails(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
    db_session: AsyncSession,
):
    # Create and manually publish
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]

    # Publish via endpoint
    await client.put(
        f"/api/v1/platform/notifications/{notif_id}/publish",
        headers=auth_headers,
    )

    response = await client.put(
        f"/api/v1/platform/notifications/{notif_id}",
        json={"title": "Should fail"},
        headers=auth_headers,
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 7. Delete draft notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_draft_notification(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
):
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/platform/notifications/{notif_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 8. Delete published notification → 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_published_notification_fails(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
):
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]

    await client.put(
        f"/api/v1/platform/notifications/{notif_id}/publish",
        headers=auth_headers,
    )

    response = await client.delete(
        f"/api/v1/platform/notifications/{notif_id}",
        headers=auth_headers,
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 9. Publish notification (fan-out)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_notification(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
    db_session: AsyncSession, verified_user: dict,
):
    await _ensure_tenant_with_owner(db_session, verified_user)

    # Create and publish
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    notif_id = create_resp.json()["id"]

    publish_resp = await client.put(
        f"/api/v1/platform/notifications/{notif_id}/publish",
        headers=auth_headers,
    )
    assert publish_resp.status_code == 200
    data = publish_resp.json()
    assert "gepubliceerd" in data["message"].lower()


# ---------------------------------------------------------------------------
# 10. User inbox (after publish)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_inbox(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
    db_session: AsyncSession, verified_user: dict,
):
    await _ensure_tenant_with_owner(db_session, verified_user)

    # Create and publish
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]
    await client.put(
        f"/api/v1/platform/notifications/{notif_id}/publish",
        headers=auth_headers,
    )

    # Check inbox
    inbox_resp = await client.get(
        "/api/v1/platform/notifications/inbox",
        headers=auth_headers,
    )
    assert inbox_resp.status_code == 200
    data = inbox_resp.json()
    assert "items" in data
    assert data["total"] >= 1


# ---------------------------------------------------------------------------
# 11. Mark notification as read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_read(
    client: AsyncClient, auth_headers: dict, notification_data: dict,
    db_session: AsyncSession, verified_user: dict,
):
    await _ensure_tenant_with_owner(db_session, verified_user)

    # Create and publish
    create_resp = await client.post(
        "/api/v1/platform/notifications",
        json=notification_data,
        headers=auth_headers,
    )
    notif_id = create_resp.json()["id"]
    await client.put(
        f"/api/v1/platform/notifications/{notif_id}/publish",
        headers=auth_headers,
    )

    # Get inbox to find recipient ID
    inbox_resp = await client.get(
        "/api/v1/platform/notifications/inbox",
        headers=auth_headers,
    )
    items = inbox_resp.json()["items"]
    if items:
        recipient_id = items[0]["id"]
        mark_resp = await client.put(
            f"/api/v1/platform/notifications/{recipient_id}/read",
            headers=auth_headers,
        )
        assert mark_resp.status_code == 200


# ---------------------------------------------------------------------------
# 12. Mark all notifications as read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_all_read(
    client: AsyncClient, auth_headers: dict,
):
    response = await client.put(
        "/api/v1/platform/notifications/read-all",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "gelezen" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# 13. Unread count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unread_count(
    client: AsyncClient, auth_headers: dict,
):
    response = await client.get(
        "/api/v1/platform/notifications/unread-count",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "count" in response.json()
    assert isinstance(response.json()["count"], int)


# ---------------------------------------------------------------------------
# 14. Get tenant preferences (defaults)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_tenant_preferences(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    response = await tenant_client.get(
        "/api/v1/org/test/notifications/platform-preferences",
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    # All should be enabled by default
    for pref in data:
        assert pref["is_enabled"] is True
        assert "type_label" in pref
        assert "type_description" in pref


# ---------------------------------------------------------------------------
# 15. Update tenant preference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_tenant_preference(
    tenant_client: AsyncClient, tenant_auth_headers: dict,
):
    response = await tenant_client.put(
        "/api/v1/org/test/notifications/platform-preferences/maintenance",
        json={"is_enabled": False, "email_enabled": False},
        headers=tenant_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_enabled"] is False
    assert data["email_enabled"] is False
    assert data["notification_type"] == "maintenance"
