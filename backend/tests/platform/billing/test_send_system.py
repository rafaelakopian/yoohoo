"""Tests for PlatformNotificationService.send_system()."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.platform.notifications.models import (
    PlatformNotification,
    PlatformNotificationRecipient,
)
from app.modules.platform.notifications.service import PlatformNotificationService


class TestSendSystem:
    @pytest.mark.asyncio
    async def test_creates_notification_without_actor(self):
        """send_system creates a notification with created_by_id=None."""
        db = AsyncMock()
        db.flush = AsyncMock()

        # Mock _get_preference → None (no preference)
        pref_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        # Mock _get_tenant_recipients → returns user IDs
        owner_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        call_count = [0]
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # _get_preference query
                return pref_mock
            elif call_count[0] == 2:
                # _get_tenant_recipients: tenant owner
                result = MagicMock()
                result.scalar_one_or_none.return_value = owner_id
                return result
            elif call_count[0] == 3:
                # _get_tenant_recipients: admin group
                result = MagicMock()
                result.scalar_one_or_none.return_value = None
                return result
            return MagicMock()

        db.execute = mock_execute

        service = PlatformNotificationService(db)

        # Patch notification type check
        with patch(
            "app.modules.platform.notifications.service.PLATFORM_NOTIFICATION_TYPES",
            {"trial.reset": MagicMock(default_severity="info")},
        ), patch(
            "app.modules.platform.notifications.service.get_type",
            return_value=MagicMock(default_severity="info"),
        ):
            await service.send_system(
                tenant_id=tenant_id,
                notification_type="trial.reset",
                title="Test notification",
                message="Test body",
            )

        # Verify notification was added
        add_calls = db.add.call_args_list
        assert len(add_calls) >= 1
        # First add = PlatformNotification
        notif = add_calls[0][0][0]
        assert isinstance(notif, PlatformNotification)
        assert notif.created_by_id is None
        assert notif.is_published is True
        assert notif.target_scope == "specific"

    @pytest.mark.asyncio
    async def test_fans_out_to_recipients(self):
        """send_system creates recipient records for tenant users."""
        db = AsyncMock()
        db.flush = AsyncMock()
        tenant_id = uuid.uuid4()
        user1 = uuid.uuid4()
        user2 = uuid.uuid4()

        call_count = [0]
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # _get_preference
                result.scalar_one_or_none.return_value = None
            elif call_count[0] == 2:
                # tenant owner
                result.scalar_one_or_none.return_value = user1
            elif call_count[0] == 3:
                # admin group
                admin_group_id = uuid.uuid4()
                result.scalar_one_or_none.return_value = admin_group_id
            elif call_count[0] == 4:
                # admin group users
                result.__iter__ = MagicMock(return_value=iter([(user2,)]))
            return result

        db.execute = mock_execute

        service = PlatformNotificationService(db)

        with patch(
            "app.modules.platform.notifications.service.PLATFORM_NOTIFICATION_TYPES",
            {"feature.blocked": MagicMock(default_severity="warning")},
        ), patch(
            "app.modules.platform.notifications.service.get_type",
            return_value=MagicMock(default_severity="warning"),
        ):
            await service.send_system(
                tenant_id=tenant_id,
                notification_type="feature.blocked",
                title="Feature blocked",
                message="Your feature is blocked",
            )

        # Should have added: 1 notification + at least 1 recipient
        add_calls = db.add.call_args_list
        assert len(add_calls) >= 2  # notification + at least one recipient
        recipients = [c[0][0] for c in add_calls if isinstance(c[0][0], PlatformNotificationRecipient)]
        assert len(recipients) >= 1

    @pytest.mark.asyncio
    async def test_works_without_arq_pool(self):
        """send_system works in cron context without arq_pool (no emails, no crash)."""
        db = AsyncMock()
        db.flush = AsyncMock()
        tenant_id = uuid.uuid4()

        async def mock_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute = mock_execute

        service = PlatformNotificationService(db)

        with patch(
            "app.modules.platform.notifications.service.PLATFORM_NOTIFICATION_TYPES",
            {"data.purged": MagicMock(default_severity="critical")},
        ), patch(
            "app.modules.platform.notifications.service.get_type",
            return_value=MagicMock(default_severity="critical"),
        ):
            # No arq_pool passed — should not crash
            result = await service.send_system(
                tenant_id=tenant_id,
                notification_type="data.purged",
                title="Data purged",
                message="Data has been purged",
                arq_pool=None,
            )

        assert isinstance(result, PlatformNotification)
