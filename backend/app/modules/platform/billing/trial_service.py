"""Trial lifecycle management for feature gating.

start_feature_trial — creates a TenantFeatureTrial record with status=trialing.
convert_trial — transitions trial to converted (tenant upgraded to a paid plan).
expire_trials — batch job: marks expired trials, transitions to retention.
purge_expired_retention — batch job: calls product purge hook, marks as purged.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.billing.models import (
    FeatureCatalog,
    FeatureTrialStatus,
    PlatformSubscription,
    TenantFeatureOverride,
    TenantFeatureTrial,
)
from app.modules.platform.billing.plan_features import PlanFeatures

logger = structlog.get_logger()

# Cooldown after expiry/cancellation before a tenant can re-trial the same feature.
TRIAL_COOLDOWN_DAYS = 90


class TrialError(Exception):
    """Raised when a trial operation fails for business logic reasons."""


class FeatureBlockedError(TrialError):
    """Raised when a feature is force-blocked via TenantFeatureOverride."""


async def _get_effective_trial_days(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    plan_trial_days: int | None,
) -> int | None:
    """Resolve effective trial_days: override → catalog → plan."""
    # 1. Tenant override
    override_result = await db.execute(
        select(TenantFeatureOverride.trial_days).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override_days = override_result.scalar_one_or_none()
    if override_days is not None:
        return override_days

    # 2. Feature catalog default
    catalog_result = await db.execute(
        select(FeatureCatalog.default_trial_days).where(
            FeatureCatalog.feature_name == feature_name,
            FeatureCatalog.is_active.is_(True),
        )
    )
    catalog_days = catalog_result.scalar_one_or_none()
    if catalog_days is not None:
        return catalog_days

    # 3. Plan features
    return plan_trial_days


async def _check_force_off(
    db: AsyncSession, tenant_id: uuid.UUID, feature_name: str,
) -> None:
    """Raise FeatureBlockedError if feature is force-blocked."""
    result = await db.execute(
        select(TenantFeatureOverride.force_off, TenantFeatureOverride.force_off_reason).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    row = result.one_or_none()
    if row and row.force_off:
        raise FeatureBlockedError(
            row.force_off_reason or "Deze feature is geblokkeerd door de beheerder."
        )


async def start_feature_trial(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    product_slug: str = "school",
) -> TenantFeatureTrial:
    """Start a feature trial for a tenant.

    Checks:
    - Feature not force-blocked
    - Feature must exist in PlanFeatures schema
    - Feature must NOT already be enabled in the tenant's active plan
    - Effective trial_days > 0 (override → catalog → plan)
    - No active trial for this feature
    - No cooldown period active (90 days after expired/cancelled)
    """
    from app.modules.platform.billing.plan_features import PlanFeatures
    from sqlalchemy.orm import selectinload

    # Check force_off
    await _check_force_off(db, tenant_id, feature_name)

    # Validate feature exists
    pf = PlanFeatures()
    feature_config = pf.get_feature(feature_name)
    if feature_config is None:
        raise TrialError(f"Onbekende feature: '{feature_name}'")

    # Get tenant's subscription + plan
    sub_result = await db.execute(
        select(PlatformSubscription)
        .options(selectinload(PlatformSubscription.plan))
        .where(PlatformSubscription.tenant_id == tenant_id)
    )
    sub = sub_result.scalar_one_or_none()

    if not sub or not sub.plan:
        raise TrialError("Geen actief abonnement gevonden.")

    plan_features = sub.plan.parsed_features

    # Feature already enabled in plan?
    if plan_features.is_feature_enabled(feature_name):
        raise TrialError(f"Feature '{feature_name}' is al inbegrepen in uw pakket.")

    # Get effective trial_days (override → catalog → plan)
    plan_trial_days = plan_features.trial_days_for(feature_name)
    trial_days = await _get_effective_trial_days(db, tenant_id, feature_name, plan_trial_days)
    if not trial_days or trial_days <= 0:
        raise TrialError(f"Er is geen proefperiode beschikbaar voor '{feature_name}'.")

    # Check existing trial record
    existing_result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.tenant_id == tenant_id,
            TenantFeatureTrial.product_slug == product_slug,
            TenantFeatureTrial.feature_name == feature_name,
        )
    )
    existing = existing_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        if existing.status == FeatureTrialStatus.trialing:
            raise TrialError("Er loopt al een proefperiode voor deze feature.")

        if existing.status == FeatureTrialStatus.converted:
            raise TrialError("Deze feature is al geconverteerd naar een betaald abonnement.")

        if existing.status == FeatureTrialStatus.retention:
            raise TrialError("Deze feature is in de retentieperiode. Upgrade om weer toegang te krijgen.")

        if existing.status == FeatureTrialStatus.purged:
            raise TrialError("De proefperiode voor deze feature is verlopen en data is verwijderd.")

        # Expired or cancelled — check cooldown (correction #11)
        if existing.status in (FeatureTrialStatus.expired, FeatureTrialStatus.cancelled):
            cooldown_end = (existing.expired_at or existing.updated_at) + timedelta(days=TRIAL_COOLDOWN_DAYS)
            if now < cooldown_end:
                days_left = (cooldown_end - now).days
                raise TrialError(
                    f"U kunt deze feature pas over {days_left} dagen opnieuw proberen."
                )
            # Cooldown passed — reset and re-trial
            existing.status = FeatureTrialStatus.trialing
            existing.trial_started_at = now
            existing.trial_expires_at = now + timedelta(days=trial_days)
            existing.trial_days_snapshot = trial_days
            existing.expired_at = None
            existing.retention_until = None
            existing.purged_at = None
            existing.warning_sent_at = None
            existing.warning_60_sent = False
            existing.warning_90_sent = False
            await db.flush()
            logger.info(
                "trial.restarted",
                tenant_id=str(tenant_id),
                feature=feature_name,
                trial_days=trial_days,
            )
            return existing

    # Create new trial
    trial = TenantFeatureTrial(
        tenant_id=tenant_id,
        product_slug=product_slug,
        feature_name=feature_name,
        status=FeatureTrialStatus.trialing,
        trial_started_at=now,
        trial_expires_at=now + timedelta(days=trial_days),
        trial_days_snapshot=trial_days,
    )
    db.add(trial)
    await db.flush()

    logger.info(
        "trial.started",
        tenant_id=str(tenant_id),
        feature=feature_name,
        trial_days=trial_days,
        expires_at=trial.trial_expires_at.isoformat(),
    )
    return trial


async def convert_trial(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    product_slug: str = "school",
) -> TenantFeatureTrial | None:
    """Mark a trial as converted (tenant upgraded to a plan that includes the feature)."""
    result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.tenant_id == tenant_id,
            TenantFeatureTrial.product_slug == product_slug,
            TenantFeatureTrial.feature_name == feature_name,
            TenantFeatureTrial.status == FeatureTrialStatus.trialing,
        )
    )
    trial = result.scalar_one_or_none()
    if not trial:
        return None

    now = datetime.now(timezone.utc)
    trial.status = FeatureTrialStatus.converted
    trial.converted_at = now
    await db.flush()

    logger.info(
        "trial.converted",
        tenant_id=str(tenant_id),
        feature=feature_name,
    )
    return trial


async def expire_trials(db: AsyncSession) -> int:
    """Expire all trials past their trial_expires_at. Returns count of expired trials.

    For each expired trial:
    - status → expired
    - If data_retention_days is configured in the plan feature → status → retention + retention_until set
    - Otherwise → status → expired (no retention, data stays)
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.status == FeatureTrialStatus.trialing,
            TenantFeatureTrial.trial_expires_at != None,  # noqa: E711
            TenantFeatureTrial.trial_expires_at <= now,
        )
    )
    trials = result.scalars().all()

    count = 0
    for trial in trials:
        # Look up retention days from the default PlanFeatures schema
        pf = PlanFeatures()
        retention_days = pf.retention_days_for(trial.feature_name)

        trial.expired_at = now

        if retention_days is not None and retention_days >= 0:
            # Move to retention period
            trial.status = FeatureTrialStatus.retention
            trial.data_retention_days = retention_days
            if retention_days == 0:
                # Immediate purge — will be caught by purge job
                trial.retention_until = now
            else:
                trial.retention_until = now + timedelta(days=retention_days)
        else:
            # No retention configured (None = permanent, data stays)
            trial.status = FeatureTrialStatus.expired

        count += 1
        logger.info(
            "trial.expired",
            tenant_id=str(trial.tenant_id),
            feature=trial.feature_name,
            has_retention=retention_days is not None,
            retention_days=retention_days,
        )

    if count:
        await db.flush()

    return count


async def purge_expired_retention(db: AsyncSession) -> int:
    """Purge data for trials whose retention period has expired. Returns count of purged trials.

    Calls the product's on_feature_data_purge hook if registered.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.status == FeatureTrialStatus.retention,
            TenantFeatureTrial.retention_until != None,  # noqa: E711
            TenantFeatureTrial.retention_until <= now,
        )
    )
    trials = result.scalars().all()

    count = 0
    for trial in trials:
        # Call product purge hook if registered
        try:
            from app.modules.platform.plugin import product_registry

            manifest = product_registry.get(trial.product_slug)
            if manifest and hasattr(manifest, "on_feature_data_purge") and manifest.on_feature_data_purge:
                await manifest.on_feature_data_purge(
                    tenant_id=trial.tenant_id,
                    feature_name=trial.feature_name,
                )
                logger.info(
                    "trial.data_purged",
                    tenant_id=str(trial.tenant_id),
                    feature=trial.feature_name,
                    product=trial.product_slug,
                )
        except Exception:
            logger.exception(
                "trial.purge_hook_failed",
                tenant_id=str(trial.tenant_id),
                feature=trial.feature_name,
            )
            # Continue — mark as purged even if hook fails (can be retried manually)

        trial.status = FeatureTrialStatus.purged
        trial.purged_at = now
        count += 1

    if count:
        await db.flush()

    return count


# ---------------------------------------------------------------------------
# Admin trial management functions (Fase H-2)
# ---------------------------------------------------------------------------


async def reset_trial(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    actor_id: uuid.UUID,
    product_slug: str = "school",
) -> TenantFeatureTrial:
    """Reset a trial for a tenant (admin action). Allows re-trial even after cooldown."""
    await _check_force_off(db, tenant_id, feature_name)

    result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.tenant_id == tenant_id,
            TenantFeatureTrial.product_slug == product_slug,
            TenantFeatureTrial.feature_name == feature_name,
        )
    )
    trial = result.scalar_one_or_none()
    if not trial:
        raise TrialError("Geen proefperiode gevonden voor deze feature.")

    # Determine effective trial_days
    plan_trial_days = None
    from sqlalchemy.orm import selectinload
    sub_result = await db.execute(
        select(PlatformSubscription)
        .options(selectinload(PlatformSubscription.plan))
        .where(PlatformSubscription.tenant_id == tenant_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub and sub.plan:
        plan_trial_days = sub.plan.parsed_features.trial_days_for(feature_name)

    effective_days = await _get_effective_trial_days(db, tenant_id, feature_name, plan_trial_days)
    if not effective_days or effective_days <= 0:
        effective_days = 14  # fallback

    now = datetime.now(timezone.utc)
    trial.status = FeatureTrialStatus.trialing
    trial.trial_started_at = now
    trial.trial_expires_at = now + timedelta(days=effective_days)
    trial.trial_days_snapshot = effective_days
    trial.expired_at = None
    trial.retention_until = None
    trial.purged_at = None
    trial.warning_sent_at = None
    trial.warning_60_sent = False
    trial.warning_90_sent = False
    trial.reset_count = (trial.reset_count or 0) + 1
    trial.reset_by_user_id = actor_id
    trial.last_reset_at = now

    await db.flush()

    logger.info(
        "trial.reset",
        tenant_id=str(tenant_id),
        feature=feature_name,
        actor_id=str(actor_id),
        reset_count=trial.reset_count,
        trial_days=effective_days,
    )
    return trial


async def extend_trial(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    extra_days: int,
    actor_id: uuid.UUID,
    product_slug: str = "school",
) -> TenantFeatureTrial:
    """Extend an active trial by extra_days (admin action)."""
    result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.tenant_id == tenant_id,
            TenantFeatureTrial.product_slug == product_slug,
            TenantFeatureTrial.feature_name == feature_name,
            TenantFeatureTrial.status == FeatureTrialStatus.trialing,
        )
    )
    trial = result.scalar_one_or_none()
    if not trial:
        raise TrialError("Geen actieve proefperiode gevonden.")

    trial.trial_expires_at = trial.trial_expires_at + timedelta(days=extra_days)
    await db.flush()

    logger.info(
        "trial.extended",
        tenant_id=str(tenant_id),
        feature=feature_name,
        extra_days=extra_days,
        new_expires_at=trial.trial_expires_at.isoformat(),
        actor_id=str(actor_id),
    )
    return trial


async def force_on(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    actor_id: uuid.UUID,
) -> TenantFeatureOverride:
    """Force-enable a feature for a tenant (admin action)."""
    result = await db.execute(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if override:
        override.force_on = True
        override.force_off = False
        override.force_off_reason = None
        override.force_off_since = None
        override.forced_by_user_id = actor_id
        override.forced_at = now
    else:
        override = TenantFeatureOverride(
            tenant_id=tenant_id,
            feature_name=feature_name,
            force_on=True,
            force_off=False,
            forced_by_user_id=actor_id,
            forced_at=now,
        )
        db.add(override)

    await db.flush()

    logger.info(
        "feature.force_on",
        tenant_id=str(tenant_id),
        feature=feature_name,
        actor_id=str(actor_id),
    )
    return override


async def force_off(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    reason: str | None,
    actor_id: uuid.UUID,
) -> TenantFeatureOverride:
    """Force-disable a feature for a tenant (admin action)."""
    result = await db.execute(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if override:
        override.force_off = True
        override.force_on = False
        override.force_off_reason = reason
        override.force_off_since = now
        override.forced_by_user_id = actor_id
        override.forced_at = now
    else:
        override = TenantFeatureOverride(
            tenant_id=tenant_id,
            feature_name=feature_name,
            force_off=True,
            force_on=False,
            force_off_reason=reason,
            force_off_since=now,
            forced_by_user_id=actor_id,
            forced_at=now,
        )
        db.add(override)

    await db.flush()

    logger.info(
        "feature.force_off",
        tenant_id=str(tenant_id),
        feature=feature_name,
        reason=reason,
        actor_id=str(actor_id),
    )
    return override


async def lift_force_off(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    feature_name: str,
    actor_id: uuid.UUID,
) -> TenantFeatureOverride:
    """Remove force-off from a feature (admin action)."""
    result = await db.execute(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override = result.scalar_one_or_none()
    if not override:
        raise TrialError("Geen override gevonden voor deze feature.")

    override.force_off = False
    override.force_off_reason = None
    override.force_off_since = None
    override.forced_by_user_id = actor_id
    override.forced_at = datetime.now(timezone.utc)

    await db.flush()

    logger.info(
        "feature.lift_force_off",
        tenant_id=str(tenant_id),
        feature=feature_name,
        actor_id=str(actor_id),
    )
    return override
