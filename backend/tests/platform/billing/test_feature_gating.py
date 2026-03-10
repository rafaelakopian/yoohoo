"""Tests for feature gating: PlanFeatures, FeatureGate, TrialService."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    FeatureTrialStatus,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
    TenantFeatureTrial,
)
from app.modules.platform.billing.plan_features import FeatureConfig, PlanFeatures
from app.modules.platform.billing.feature_gate import FeatureAccess, check_feature_access
from app.modules.platform.billing.trial_service import (
    TRIAL_COOLDOWN_DAYS,
    TrialError,
    convert_trial,
    expire_trials,
    purge_expired_retention,
    start_feature_trial,
)


# ─── PlanFeatures Unit Tests (no DB needed) ───


class TestPlanFeatures:
    def test_default_base_features_enabled(self):
        pf = PlanFeatures()
        assert pf.student_management.enabled is True
        assert pf.attendance.enabled is True
        assert pf.schedule.enabled is True
        assert pf.notifications.enabled is True

    def test_default_expandable_features_disabled(self):
        pf = PlanFeatures()
        assert pf.billing.enabled is False
        assert pf.collaborations.enabled is False
        assert pf.reporting.enabled is False
        assert pf.api_access.enabled is False
        assert pf.custom_branding.enabled is False
        assert pf.priority_support.enabled is False

    def test_is_feature_enabled(self):
        pf = PlanFeatures(billing=FeatureConfig(enabled=True))
        assert pf.is_feature_enabled("billing") is True
        assert pf.is_feature_enabled("reporting") is False

    def test_is_feature_enabled_unknown(self):
        pf = PlanFeatures()
        assert pf.is_feature_enabled("nonexistent") is False

    def test_trial_days_for(self):
        pf = PlanFeatures(billing=FeatureConfig(trial_days=14))
        assert pf.trial_days_for("billing") == 14
        assert pf.trial_days_for("reporting") is None  # default

    def test_retention_days_for(self):
        pf = PlanFeatures(billing=FeatureConfig(data_retention_days=30))
        assert pf.retention_days_for("billing") == 30
        assert pf.retention_days_for("reporting") is None  # default = permanent

    def test_get_feature_unknown(self):
        pf = PlanFeatures()
        assert pf.get_feature("nonexistent") is None

    def test_roundtrip_json(self):
        pf = PlanFeatures(
            billing=FeatureConfig(enabled=True, trial_days=14, data_retention_days=30),
            reporting=FeatureConfig(enabled=False, trial_days=7),
        )
        data = pf.model_dump()
        restored = PlanFeatures(**data)
        assert restored.billing.enabled is True
        assert restored.billing.trial_days == 14
        assert restored.billing.data_retention_days == 30
        assert restored.reporting.trial_days == 7
        assert restored.student_management.enabled is True

    def test_feature_config_defaults(self):
        fc = FeatureConfig()
        assert fc.enabled is False
        assert fc.trial_days is None
        assert fc.data_retention_days is None


# ─── FeatureAccess Model Tests (no DB needed) ───


class TestFeatureAccess:
    def test_allowed(self):
        fa = FeatureAccess(allowed=True)
        assert fa.allowed is True
        assert fa.in_trial is False
        assert fa.trial_available is False
        assert fa.in_retention is False

    def test_denied_with_trial(self):
        fa = FeatureAccess(
            allowed=False,
            trial_available=True,
            trial_days=14,
            reason="Not in plan",
        )
        assert fa.allowed is False
        assert fa.trial_available is True
        assert fa.trial_days == 14

    def test_in_trial(self):
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        fa = FeatureAccess(
            allowed=True,
            in_trial=True,
            trial_expires_at=expires,
        )
        assert fa.allowed is True
        assert fa.in_trial is True

    def test_in_retention(self):
        fa = FeatureAccess(
            allowed=False,
            in_retention=True,
            reason="Data in retention",
        )
        assert fa.in_retention is True
        assert fa.allowed is False


# ─── TrialService Unit Tests (no DB needed) ───


class TestTrialCooldown:
    def test_cooldown_days_configured(self):
        assert TRIAL_COOLDOWN_DAYS == 90


class TestTrialError:
    def test_trial_error_is_exception(self):
        err = TrialError("test message")
        assert str(err) == "test message"
        assert isinstance(err, Exception)


# ─── DB-dependent Tests ───
# These require PostgreSQL (Docker) and will show as ERROR without it.


@pytest_asyncio.fixture
async def billing_tenant_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a test tenant for billing tests."""
    from app.modules.platform.tenant_mgmt.models import Tenant

    tenant = Tenant(
        name="Feature Gate Test School",
        slug=f"fg-test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant.id


@pytest_asyncio.fixture
async def plan_with_billing_trial(db_session: AsyncSession) -> PlatformPlan:
    """Create a plan where billing has trial_days=14 but is NOT enabled."""
    plan = PlatformPlan(
        name="Starter",
        slug=f"starter-fg-{uuid.uuid4().hex[:8]}",
        price_cents=2900,
        currency="EUR",
        interval="monthly",
        is_active=True,
        sort_order=1,
        features=PlanFeatures(
            billing=FeatureConfig(enabled=False, trial_days=14, data_retention_days=30),
        ).model_dump(),
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


@pytest_asyncio.fixture
async def plan_with_billing_enabled(db_session: AsyncSession) -> PlatformPlan:
    """Create a plan where billing IS enabled."""
    plan = PlatformPlan(
        name="Pro",
        slug=f"pro-fg-{uuid.uuid4().hex[:8]}",
        price_cents=5900,
        currency="EUR",
        interval="monthly",
        is_active=True,
        sort_order=2,
        features=PlanFeatures(
            billing=FeatureConfig(enabled=True),
            reporting=FeatureConfig(enabled=True),
        ).model_dump(),
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


@pytest_asyncio.fixture
async def subscription(
    db_session: AsyncSession,
    billing_tenant_id: uuid.UUID,
    plan_with_billing_trial: PlatformPlan,
) -> PlatformSubscription:
    """Create an active subscription on the starter plan."""
    sub = PlatformSubscription(
        tenant_id=billing_tenant_id,
        plan_id=plan_with_billing_trial.id,
        status=SubscriptionStatus.active,
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


@pytest.mark.asyncio
class TestCheckFeatureAccess:
    async def test_feature_in_plan_allowed(
        self, db_session: AsyncSession, billing_tenant_id, plan_with_billing_enabled
    ):
        """Feature enabled in plan → allowed."""
        sub = PlatformSubscription(
            tenant_id=billing_tenant_id,
            plan_id=plan_with_billing_enabled.id,
            status=SubscriptionStatus.active,
        )
        db_session.add(sub)
        await db_session.flush()

        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is True

    async def test_feature_not_in_plan_denied(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Feature not enabled in plan → denied with trial info."""
        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is False
        assert access.trial_available is True
        assert access.trial_days == 14

    async def test_active_trial_allowed(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Active trial → allowed."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.trialing,
            trial_started_at=now,
            trial_expires_at=now + timedelta(days=14),
        )
        db_session.add(trial)
        await db_session.flush()

        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is True
        assert access.in_trial is True

    async def test_retention_denied_403(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Feature in retention → denied with in_retention=True."""
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.retention,
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(trial)
        await db_session.flush()

        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is False
        assert access.in_retention is True

    async def test_no_subscription_denied(self, db_session: AsyncSession, billing_tenant_id):
        """No subscription → denied without trial info."""
        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is False
        assert access.trial_available is False

    async def test_upgrade_plans_listed(
        self, db_session: AsyncSession, billing_tenant_id, subscription, plan_with_billing_enabled
    ):
        """Denied feature → lists plans that include the feature."""
        access = await check_feature_access(billing_tenant_id, "billing", db=db_session)
        assert access.allowed is False
        assert len(access.upgrade_plans) >= 1
        assert any(p["name"] == "Pro" for p in access.upgrade_plans)


@pytest.mark.asyncio
class TestStartFeatureTrial:
    async def test_start_trial_success(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Start a trial for a feature with trial_days configured."""
        trial = await start_feature_trial(db_session, billing_tenant_id, "billing")
        assert trial.status == FeatureTrialStatus.trialing
        assert trial.trial_expires_at is not None
        assert trial.trial_started_at is not None

    async def test_start_trial_unknown_feature(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Unknown feature → TrialError."""
        with pytest.raises(TrialError, match="Onbekende feature"):
            await start_feature_trial(db_session, billing_tenant_id, "nonexistent_feature")

    async def test_start_trial_feature_already_enabled(
        self, db_session: AsyncSession, billing_tenant_id, plan_with_billing_enabled
    ):
        """Feature already in plan → TrialError."""
        sub = PlatformSubscription(
            tenant_id=billing_tenant_id,
            plan_id=plan_with_billing_enabled.id,
            status=SubscriptionStatus.active,
        )
        db_session.add(sub)
        await db_session.flush()

        with pytest.raises(TrialError, match="al inbegrepen"):
            await start_feature_trial(db_session, billing_tenant_id, "billing")

    async def test_start_trial_already_trialing(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Already trialing → TrialError."""
        await start_feature_trial(db_session, billing_tenant_id, "billing")
        with pytest.raises(TrialError, match="loopt al"):
            await start_feature_trial(db_session, billing_tenant_id, "billing")

    async def test_start_trial_cooldown_active(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Expired trial within cooldown → TrialError with days remaining."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.expired,
            trial_started_at=now - timedelta(days=14),
            trial_expires_at=now,
            expired_at=now,
        )
        db_session.add(trial)
        await db_session.flush()

        with pytest.raises(TrialError, match="opnieuw proberen"):
            await start_feature_trial(db_session, billing_tenant_id, "billing")

    async def test_start_trial_cooldown_passed(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Expired trial past cooldown → trial restarts."""
        now = datetime.now(timezone.utc)
        expired_at = now - timedelta(days=TRIAL_COOLDOWN_DAYS + 1)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.expired,
            trial_started_at=expired_at - timedelta(days=14),
            trial_expires_at=expired_at,
            expired_at=expired_at,
        )
        db_session.add(trial)
        await db_session.flush()

        restarted = await start_feature_trial(db_session, billing_tenant_id, "billing")
        assert restarted.status == FeatureTrialStatus.trialing
        assert restarted.trial_expires_at > now


@pytest.mark.asyncio
class TestConvertTrial:
    async def test_convert_active_trial(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Convert an active trial → status becomes converted."""
        trial = await start_feature_trial(db_session, billing_tenant_id, "billing")
        assert trial.status == FeatureTrialStatus.trialing

        converted = await convert_trial(db_session, billing_tenant_id, "billing")
        assert converted is not None
        assert converted.status == FeatureTrialStatus.converted
        assert converted.converted_at is not None

    async def test_convert_no_trial(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """No active trial → returns None."""
        result = await convert_trial(db_session, billing_tenant_id, "billing")
        assert result is None


@pytest.mark.asyncio
class TestExpireTrials:
    async def test_expire_past_trials(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Trials past their expires_at get expired."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.trialing,
            trial_started_at=now - timedelta(days=15),
            trial_expires_at=now - timedelta(days=1),
        )
        db_session.add(trial)
        await db_session.flush()

        count = await expire_trials(db_session)
        assert count == 1

        await db_session.refresh(trial)
        # Should be retention (billing has data_retention_days=None in default PlanFeatures)
        assert trial.status in (FeatureTrialStatus.expired, FeatureTrialStatus.retention)
        assert trial.expired_at is not None

    async def test_expire_skips_active_trials(
        self, db_session: AsyncSession, billing_tenant_id, subscription
    ):
        """Trials not yet expired are skipped."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.trialing,
            trial_started_at=now,
            trial_expires_at=now + timedelta(days=14),
        )
        db_session.add(trial)
        await db_session.flush()

        count = await expire_trials(db_session)
        assert count == 0

        await db_session.refresh(trial)
        assert trial.status == FeatureTrialStatus.trialing


@pytest.mark.asyncio
class TestPurgeExpiredRetention:
    async def test_purge_past_retention(
        self, db_session: AsyncSession, billing_tenant_id
    ):
        """Trials past retention_until get purged."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.retention,
            retention_until=now - timedelta(days=1),
            data_retention_days=30,
        )
        db_session.add(trial)
        await db_session.flush()

        count = await purge_expired_retention(db_session)
        assert count == 1

        await db_session.refresh(trial)
        assert trial.status == FeatureTrialStatus.purged
        assert trial.purged_at is not None

    async def test_purge_skips_future_retention(
        self, db_session: AsyncSession, billing_tenant_id
    ):
        """Trials still in retention are skipped."""
        now = datetime.now(timezone.utc)
        trial = TenantFeatureTrial(
            tenant_id=billing_tenant_id,
            product_slug="school",
            feature_name="billing",
            status=FeatureTrialStatus.retention,
            retention_until=now + timedelta(days=10),
            data_retention_days=30,
        )
        db_session.add(trial)
        await db_session.flush()

        count = await purge_expired_retention(db_session)
        assert count == 0

        await db_session.refresh(trial)
        assert trial.status == FeatureTrialStatus.retention
