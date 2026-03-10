"""FeatureGate — checks whether a tenant has access to a feature.

Usage on endpoints:
    @router.get("/billing/invoices")
    async def list_invoices(
        _: None = Depends(require_feature("billing")),
        ...
    ):

Raises HTTP 402 with upgrade info when feature is unavailable.
Raises HTTP 403 when data is in retention period (feature expired, data
still present but no longer usable).
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.central import get_central_db
from app.modules.platform.billing.models import (
    FeatureTrialStatus,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
    TenantFeatureOverride,
    TenantFeatureTrial,
)

# Subscription statuses that grant plan-based feature access
_ACTIVE_SUB_STATUSES = {SubscriptionStatus.active, SubscriptionStatus.trialing}

logger = structlog.get_logger()


class FeatureAccess(BaseModel):
    allowed: bool
    reason: str | None = None
    in_trial: bool = False
    trial_available: bool = False
    trial_days: int | None = None
    trial_expires_at: datetime | None = None
    in_retention: bool = False
    is_force_blocked: bool = False
    is_force_enabled: bool = False
    force_off_reason: str | None = None
    upgrade_plans: list[dict] = []


async def check_feature_access(
    tenant_id: uuid.UUID,
    feature_name: str,
    product_slug: str = "school",
    db: AsyncSession | None = None,
) -> FeatureAccess:
    """Determine whether a tenant has access to a feature.

    Priority order:
    1. force_off override → always blocked
    2. force_on override → always allowed
    3. Plan enabled → allowed
    4. Active trial → allowed
    5. Retention → denied (403)
    6. Trial available → denied with trial info (402)
    7. Otherwise → denied with upgrade plans (402)
    """
    if db is None:
        return FeatureAccess(allowed=False, reason="Geen databaseverbinding")

    # 1. Check tenant feature override (force_off / force_on)
    override_result = await db.execute(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_name == feature_name,
        )
    )
    override = override_result.scalar_one_or_none()

    if override and override.force_off:
        return FeatureAccess(
            allowed=False,
            reason=override.force_off_reason or "Deze feature is uitgeschakeld door de beheerder.",
            is_force_blocked=True,
            force_off_reason=override.force_off_reason,
        )

    if override and override.force_on:
        return FeatureAccess(
            allowed=True,
            is_force_enabled=True,
        )

    # 3. Get subscription + plan (only grant access for active/trialing subs)
    result = await db.execute(
        select(PlatformSubscription)
        .options(selectinload(PlatformSubscription.plan))
        .where(PlatformSubscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()

    if sub and sub.plan and sub.status in _ACTIVE_SUB_STATUSES:
        pf = sub.plan.parsed_features
        if pf.is_feature_enabled(feature_name):
            return FeatureAccess(allowed=True)

        # Feature not in plan — check trial availability
        trial_days = pf.trial_days_for(feature_name)
    elif sub and sub.plan:
        # Subscription exists but is paused/cancelled/expired — no plan features
        trial_days = None
    else:
        trial_days = None

    # 4. Check active trial
    now = datetime.now(timezone.utc)
    trial_result = await db.execute(
        select(TenantFeatureTrial).where(
            TenantFeatureTrial.tenant_id == tenant_id,
            TenantFeatureTrial.product_slug == product_slug,
            TenantFeatureTrial.feature_name == feature_name,
        )
    )
    trial = trial_result.scalar_one_or_none()

    if trial:
        if trial.status == FeatureTrialStatus.trialing and trial.trial_expires_at and trial.trial_expires_at > now:
            return FeatureAccess(
                allowed=True,
                in_trial=True,
                trial_expires_at=trial.trial_expires_at,
            )
        if trial.status == FeatureTrialStatus.retention:
            return FeatureAccess(
                allowed=False,
                reason="Feature is verlopen. Uw data wordt bewaard tot de retentieperiode afloopt.",
                in_retention=True,
            )

    # 5. Build upgrade plans list
    plans_result = await db.execute(
        select(PlatformPlan).where(PlatformPlan.is_active.is_(True)).order_by(PlatformPlan.sort_order)
    )
    all_plans = plans_result.scalars().all()
    upgrade_plans = []
    for p in all_plans:
        if p.parsed_features.is_feature_enabled(feature_name):
            upgrade_plans.append({
                "id": str(p.id),
                "name": p.name,
                "slug": p.slug,
                "price_cents": p.price_cents,
                "interval": p.interval.value if hasattr(p.interval, "value") else p.interval,
            })

    # 6. Determine if trial is available
    can_trial = (
        trial_days is not None
        and trial_days > 0
        and (trial is None or trial.status not in (
            FeatureTrialStatus.expired,
            FeatureTrialStatus.cancelled,
            FeatureTrialStatus.retention,
            FeatureTrialStatus.purged,
        ))
    )

    return FeatureAccess(
        allowed=False,
        reason=f"Feature '{feature_name}' is niet beschikbaar in uw huidige pakket.",
        trial_available=can_trial,
        trial_days=trial_days if can_trial else None,
        upgrade_plans=upgrade_plans,
    )


def require_feature(feature_name: str, product_slug: str = "school"):
    """FastAPI dependency factory. Usage: Depends(require_feature("billing"))"""

    async def dependency(
        request: Request,
        db: AsyncSession = Depends(get_central_db),
    ) -> None:
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context vereist")

        access = await check_feature_access(
            tenant_id=tenant_id,
            feature_name=feature_name,
            product_slug=product_slug,
            db=db,
        )
        if access.is_force_blocked:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "feature_force_blocked",
                    "feature": feature_name,
                    "message": access.reason,
                    "force_off_reason": access.force_off_reason,
                },
            )
        if access.in_retention:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "feature_in_retention",
                    "feature": feature_name,
                    "message": access.reason,
                },
            )
        if not access.allowed:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "feature_not_available",
                    "feature": feature_name,
                    "trial_available": access.trial_available,
                    "trial_days": access.trial_days,
                    "upgrade_plans": access.upgrade_plans,
                    "message": access.reason,
                },
            )

    return dependency
