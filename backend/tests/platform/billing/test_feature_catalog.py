"""Tests for feature catalog, force_off/force_on priority, and override trial_days."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.billing.models import (
    FeatureCatalog,
    FeatureTrialStatus,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
    TenantFeatureOverride,
    TenantFeatureTrial,
)
from app.modules.platform.billing.plan_features import PlanFeatures
from app.modules.platform.billing.feature_gate import check_feature_access
from app.modules.platform.billing.trial_service import (
    FeatureBlockedError,
    start_feature_trial,
)


def _mock_db():
    """Create a mock AsyncSession for unit tests."""
    db = AsyncMock()
    return db


def _mock_override(force_on=False, force_off=False, reason=None, trial_days=None):
    """Build a mock TenantFeatureOverride."""
    override = MagicMock(spec=TenantFeatureOverride)
    override.force_on = force_on
    override.force_off = force_off
    override.force_off_reason = reason
    override.trial_days = trial_days
    return override


def _mock_plan(features_dict=None, slug="pro"):
    plan = MagicMock(spec=PlatformPlan)
    plan.id = uuid.uuid4()
    plan.name = "Pro"
    plan.slug = slug
    plan.price_cents = 4999
    plan.interval = "monthly"
    plan.is_active = True
    plan.sort_order = 1
    if features_dict:
        plan.parsed_features = PlanFeatures(**features_dict)
    else:
        plan.parsed_features = PlanFeatures()
    return plan


def _mock_sub(plan=None, tenant_id=None):
    sub = MagicMock(spec=PlatformSubscription)
    sub.tenant_id = tenant_id or uuid.uuid4()
    sub.plan = plan or _mock_plan()
    sub.status = SubscriptionStatus.active
    return sub


class TestFeatureCatalogUpsert:
    def test_catalog_model_fields(self):
        """FeatureCatalog model has expected attributes."""
        catalog = FeatureCatalog(
            feature_name="billing",
            display_name="Facturatie",
            description="Facturen en betalingen",
            default_trial_days=14,
            default_retention_days=90,
            is_active=True,
        )
        assert catalog.feature_name == "billing"
        assert catalog.display_name == "Facturatie"
        assert catalog.default_trial_days == 14
        assert catalog.default_retention_days == 90
        assert catalog.is_active is True

    def test_catalog_update(self):
        """FeatureCatalog fields can be updated."""
        catalog = FeatureCatalog(
            feature_name="billing",
            display_name="Facturatie",
            default_trial_days=14,
            default_retention_days=90,
        )
        catalog.display_name = "Facturatie Pro"
        catalog.default_trial_days = 30
        assert catalog.display_name == "Facturatie Pro"
        assert catalog.default_trial_days == 30


class TestCheckFeatureAccessPriority:
    """Tests that check_feature_access follows the correct priority order."""

    @pytest.mark.asyncio
    async def test_force_off_highest_priority(self):
        """force_off override always blocks, even if plan enables the feature."""
        db = _mock_db()
        tenant_id = uuid.uuid4()

        # Override query: force_off=True
        override = _mock_override(force_off=True, reason="Misbruik gedetecteerd")
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=override))

        result = await check_feature_access(tenant_id, "billing", db=db)
        assert result.allowed is False
        assert result.is_force_blocked is True
        assert result.force_off_reason == "Misbruik gedetecteerd"

    @pytest.mark.asyncio
    async def test_force_on_second_priority(self):
        """force_on overrides plan and trial checks."""
        db = _mock_db()
        tenant_id = uuid.uuid4()

        # 1st call: override → force_on
        override = _mock_override(force_on=True)
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=override))

        result = await check_feature_access(tenant_id, "billing", db=db)
        assert result.allowed is True
        assert result.is_force_enabled is True

    @pytest.mark.asyncio
    async def test_plan_third_priority(self):
        """Plan-enabled feature returns allowed when no override exists."""
        db = _mock_db()
        tenant_id = uuid.uuid4()
        plan = _mock_plan({"billing": {"enabled": True}})
        sub = _mock_sub(plan=plan, tenant_id=tenant_id)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # Override query: None
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 2:
                # Subscription query
                mock_result.scalar_one_or_none.return_value = sub
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await check_feature_access(tenant_id, "billing", db=db)
        assert result.allowed is True
        assert result.is_force_blocked is False
        assert result.is_force_enabled is False

    @pytest.mark.asyncio
    async def test_active_trial_fourth_priority(self):
        """Active trial returns allowed when no override and not in plan."""
        db = _mock_db()
        tenant_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        trial = MagicMock(spec=TenantFeatureTrial)
        trial.status = FeatureTrialStatus.trialing
        trial.trial_expires_at = now + timedelta(days=7)

        sub = _mock_sub(tenant_id=tenant_id)  # billing not enabled in plan

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = None  # no override
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = sub  # subscription
            elif call_count[0] == 3:
                mock_result.scalar_one_or_none.return_value = trial  # active trial
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await check_feature_access(tenant_id, "billing", db=db)
        assert result.allowed is True
        assert result.in_trial is True

    @pytest.mark.asyncio
    async def test_locked_when_nothing_applies(self):
        """Returns not allowed when no override, not in plan, no trial."""
        db = _mock_db()
        tenant_id = uuid.uuid4()
        sub = _mock_sub(tenant_id=tenant_id)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = None  # no override
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = sub  # subscription
            elif call_count[0] == 3:
                mock_result.scalar_one_or_none.return_value = None  # no trial
            elif call_count[0] == 4:
                mock_result.scalars.return_value.all.return_value = []  # no upgrade plans
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await check_feature_access(tenant_id, "billing", db=db)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_start_trial_blocked_by_force_off(self):
        """start_feature_trial raises FeatureBlockedError when force_off is active."""
        db = _mock_db()
        tenant_id = uuid.uuid4()

        # _check_force_off query: force_off=True
        row = MagicMock()
        row.force_off = True
        row.force_off_reason = "Account opgeschort"
        db.execute.return_value = MagicMock(one_or_none=MagicMock(return_value=row))

        with pytest.raises(FeatureBlockedError, match="Account opgeschort"):
            await start_feature_trial(db, tenant_id, "billing")


class TestOverrideTrialDays:
    @pytest.mark.asyncio
    async def test_get_offer_prefers_tenant_override(self):
        """Tenant override trial_days takes precedence over catalog and plan."""
        from app.modules.platform.billing.trial_service import _get_effective_trial_days

        db = _mock_db()
        tenant_id = uuid.uuid4()

        # Override query returns trial_days=30
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=30))

        result = await _get_effective_trial_days(db, tenant_id, "billing", plan_trial_days=14)
        assert result == 30

    @pytest.mark.asyncio
    async def test_get_offer_falls_back_to_catalog(self):
        """Falls back to catalog default_trial_days when no tenant override."""
        from app.modules.platform.billing.trial_service import _get_effective_trial_days

        db = _mock_db()
        tenant_id = uuid.uuid4()

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = None  # no override
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = 21  # catalog default
            return mock_result

        db.execute = AsyncMock(side_effect=side_effect)

        result = await _get_effective_trial_days(db, tenant_id, "billing", plan_trial_days=14)
        assert result == 21

    @pytest.mark.asyncio
    async def test_get_offer_falls_back_to_plan(self):
        """Falls back to plan trial_days when no override and no catalog entry."""
        from app.modules.platform.billing.trial_service import _get_effective_trial_days

        db = _mock_db()
        tenant_id = uuid.uuid4()

        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await _get_effective_trial_days(db, tenant_id, "billing", plan_trial_days=14)
        assert result == 14
