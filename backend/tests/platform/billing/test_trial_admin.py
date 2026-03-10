"""Tests for admin trial management: reset, extend, force_on, force_off, lift."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.billing.models import (
    FeatureTrialStatus,
    PlatformSubscription,
    TenantFeatureOverride,
    TenantFeatureTrial,
)
from app.modules.platform.billing.trial_service import (
    FeatureBlockedError,
    TrialError,
    extend_trial,
    force_off,
    force_on,
    lift_force_off,
    reset_trial,
)


def _make_trial(
    tenant_id=None,
    feature_name="billing",
    status=FeatureTrialStatus.expired,
    trial_days_snapshot=14,
    reset_count=0,
    trial_expires_at=None,
):
    trial = MagicMock(spec=TenantFeatureTrial)
    trial.tenant_id = tenant_id or uuid.uuid4()
    trial.product_slug = "school"
    trial.feature_name = feature_name
    trial.status = status
    trial.trial_days_snapshot = trial_days_snapshot
    trial.reset_count = reset_count
    trial.trial_expires_at = trial_expires_at or datetime.now(timezone.utc) - timedelta(days=1)
    trial.expired_at = None
    trial.retention_until = None
    trial.purged_at = None
    trial.warning_sent_at = None
    trial.warning_60_sent = False
    trial.warning_90_sent = False
    trial.trial_started_at = None
    trial.reset_by_user_id = None
    trial.last_reset_at = None
    return trial


class TestResetTrial:
    @pytest.mark.asyncio
    async def test_reset_increases_reset_count(self):
        """reset_trial increments reset_count."""
        db = AsyncMock()
        tenant_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        trial = _make_trial(tenant_id=tenant_id, reset_count=2)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # _check_force_off: no force_off
                mock_result.one_or_none.return_value = None
            elif call_count[0] == 2:
                # select trial
                mock_result.scalar_one_or_none.return_value = trial
            elif call_count[0] == 3:
                # subscription query
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 4:
                # override trial_days
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 5:
                # catalog trial_days
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await reset_trial(db, tenant_id, "billing", actor_id)
        assert result.reset_count == 3
        assert result.status == FeatureTrialStatus.trialing

    @pytest.mark.asyncio
    async def test_reset_snapshots_trial_days(self):
        """reset_trial stores effective trial_days in trial_days_snapshot."""
        db = AsyncMock()
        tenant_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        trial = _make_trial(tenant_id=tenant_id)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.one_or_none.return_value = None  # no force_off
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = trial
            elif call_count[0] == 3:
                mock_result.scalar_one_or_none.return_value = None  # no sub
            elif call_count[0] == 4:
                mock_result.scalar_one_or_none.return_value = None  # no override
            elif call_count[0] == 5:
                mock_result.scalar_one_or_none.return_value = 21  # catalog: 21 days
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await reset_trial(db, tenant_id, "billing", actor_id)
        assert result.trial_days_snapshot == 21

    @pytest.mark.asyncio
    async def test_reset_blocked_by_force_off(self):
        """reset_trial raises FeatureBlockedError when force_off is active."""
        db = AsyncMock()
        row = MagicMock()
        row.force_off = True
        row.force_off_reason = "Overtreding"
        db.execute.return_value = MagicMock(one_or_none=MagicMock(return_value=row))

        with pytest.raises(FeatureBlockedError, match="Overtreding"):
            await reset_trial(db, uuid.uuid4(), "billing", uuid.uuid4())


class TestExtendTrial:
    @pytest.mark.asyncio
    async def test_extend_shifts_expires_at(self):
        """extend_trial adds extra_days to trial_expires_at."""
        db = AsyncMock()
        tenant_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        trial = _make_trial(
            tenant_id=tenant_id,
            status=FeatureTrialStatus.trialing,
            trial_expires_at=now + timedelta(days=7),
        )

        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=trial))

        result = await extend_trial(db, tenant_id, "billing", 10, uuid.uuid4())
        expected = now + timedelta(days=17)
        assert abs((result.trial_expires_at - expected).total_seconds()) < 2


class TestForceOnOff:
    @pytest.mark.asyncio
    async def test_force_off_creates_override(self):
        """force_off creates a new TenantFeatureOverride with force_off=True."""
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await force_off(db, uuid.uuid4(), "billing", "Test reden", uuid.uuid4())
        assert result.force_off is True
        assert result.force_on is False
        assert result.force_off_reason == "Test reden"
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_on_creates_override(self):
        """force_on creates override with force_on=True, force_off=False."""
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await force_on(db, uuid.uuid4(), "billing", uuid.uuid4())
        assert result.force_on is True
        assert result.force_off is False
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_lift_force_off_clears_block(self):
        """lift_force_off resets force_off fields on existing override."""
        db = AsyncMock()
        override = MagicMock(spec=TenantFeatureOverride)
        override.force_off = True
        override.force_off_reason = "Was geblokkeerd"
        override.force_off_since = datetime.now(timezone.utc)
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=override))

        result = await lift_force_off(db, uuid.uuid4(), "billing", uuid.uuid4())
        assert result.force_off is False
        assert result.force_off_reason is None
        assert result.force_off_since is None
