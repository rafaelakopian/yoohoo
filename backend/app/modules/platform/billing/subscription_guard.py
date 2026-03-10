"""Subscription access guard — blocks tenant routes for paused/cancelled/expired subscriptions.

Applied as a router-level dependency on the tenant parent router.
Runs AFTER resolve_tenant_from_path (which sets request.state.tenant_id).

Whitelisted path prefixes are always allowed (billing, upgrade, features, access).
"""

import time
import uuid

import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.central import get_central_db
from app.modules.platform.billing.models import (
    PlatformSubscription,
    SubscriptionStatus,
)

logger = structlog.get_logger()

# Subscription statuses that allow full tenant access
_ALLOWED_STATUSES = {
    SubscriptionStatus.active,
    SubscriptionStatus.trialing,
    SubscriptionStatus.past_due,
}

# Path suffixes (after /org/{slug}) that remain accessible even when paused/cancelled
_WHITELIST_SUFFIXES = (
    "/billing",
    "/upgrade",
    "/features",
    "/access",
    "/notifications/platform-preferences",
)

# In-memory cache: tenant_id -> (status, plan_name, cancelled_at_iso, timestamp)
_sub_status_cache: dict[uuid.UUID, tuple[str, str | None, str | None, float]] = {}
_CACHE_TTL = 300  # 5 minutes (same as slug-to-id cache)


async def _lookup_subscription_status(
    tenant_id: uuid.UUID, db: AsyncSession
) -> tuple[str, str | None, str | None]:
    """Look up subscription status for a tenant, with in-memory cache."""
    cached = _sub_status_cache.get(tenant_id)
    if cached is not None:
        status, plan_name, cancelled_at, ts = cached
        if time.monotonic() - ts < _CACHE_TTL:
            return status, plan_name, cancelled_at

    result = await db.execute(
        select(PlatformSubscription)
        .options(selectinload(PlatformSubscription.plan))
        .where(PlatformSubscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        # No subscription at all — treat as allowed (free tier / not yet subscribed)
        _sub_status_cache[tenant_id] = ("none", None, None, time.monotonic())
        return "none", None, None

    status = sub.status.value if hasattr(sub.status, "value") else sub.status
    plan_name = sub.plan.name if sub.plan else None
    cancelled_at = sub.cancelled_at.isoformat() if sub.cancelled_at else None

    _sub_status_cache[tenant_id] = (status, plan_name, cancelled_at, time.monotonic())
    return status, plan_name, cancelled_at


def invalidate_sub_status_cache(tenant_id: uuid.UUID) -> None:
    """Remove a tenant from the subscription status cache."""
    _sub_status_cache.pop(tenant_id, None)


def clear_sub_status_cache() -> None:
    """Clear entire subscription status cache."""
    _sub_status_cache.clear()


def _is_whitelisted(path: str, slug: str) -> bool:
    """Check if a request path is in the whitelist for paused tenants."""
    prefix = f"/api/v1/org/{slug}"
    suffix = path[len(prefix):] if path.startswith(prefix) else ""
    # Also allow the subscription-status endpoint itself
    if suffix == "/subscription-status":
        return True
    return any(suffix == wl or suffix.startswith(wl + "/") for wl in _WHITELIST_SUFFIXES)


async def require_active_subscription(
    request: Request,
    db: AsyncSession = Depends(get_central_db),
) -> None:
    """Block tenant access when subscription is paused/cancelled/expired.

    Whitelisted paths (billing, upgrade, features, access) remain accessible.
    No subscription = allowed (free tier / onboarding).
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return  # No tenant context — not a tenant route

    slug = getattr(request.state, "tenant_slug", "")
    status, plan_name, _cancelled_at = await _lookup_subscription_status(tenant_id, db)

    # No subscription or active status → pass through
    if status == "none" or status in {s.value for s in _ALLOWED_STATUSES}:
        return

    # Inactive subscription — check whitelist
    if _is_whitelisted(request.url.path, slug):
        return

    # Store status on request for downstream use
    request.state.subscription_status = status

    detail_code = "subscription_paused" if status == "paused" else "subscription_inactive"
    logger.info(
        "subscription_guard.blocked",
        tenant_id=str(tenant_id),
        status=status,
        path=request.url.path,
    )

    raise HTTPException(
        status_code=403,
        detail={
            "code": detail_code,
            "status": status,
            "plan_name": plan_name,
            "slug": slug,
            "message": "Abonnement is niet actief. Ga naar de upgrade-pagina om je abonnement te heractiveren.",
        },
    )
