"""Resolve tenant context from URL path slug.

Used as a router-level dependency on the tenant parent router.
Replaces the X-Tenant-ID header approach with slug-in-URL.
"""

import time
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db

import structlog

logger = structlog.get_logger()

# In-memory cache: slug -> (tenant_id, timestamp)
_slug_to_id_cache: dict[str, tuple[uuid.UUID, float]] = {}
_CACHE_TTL = 300  # 5 minutes


async def _lookup_tenant_by_slug(slug: str, db: AsyncSession) -> uuid.UUID | None:
    """Look up tenant UUID by slug, with in-memory cache."""
    cached = _slug_to_id_cache.get(slug)
    if cached is not None:
        tenant_id, ts = cached
        if time.monotonic() - ts < _CACHE_TTL:
            return tenant_id
        del _slug_to_id_cache[slug]

    result = await db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug AND is_active = true"),
        {"slug": slug},
    )
    row = result.first()
    if row is None:
        return None

    tenant_id = row[0]
    _slug_to_id_cache[slug] = (tenant_id, time.monotonic())
    return tenant_id


async def resolve_tenant_from_path(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
) -> None:
    """Resolve tenant from URL path {slug} and set request.state.

    This dependency is applied at the router level on the tenant parent router.
    It runs before any endpoint dependencies (get_tenant_db, require_permission).
    """
    tenant_id = await _lookup_tenant_by_slug(slug, db)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    request.state.tenant_id = tenant_id
    request.state.tenant_slug = slug

    structlog.contextvars.bind_contextvars(
        tenant_id=str(tenant_id), tenant_slug=slug
    )


def invalidate_slug_to_id_cache(slug: str) -> None:
    """Remove a slug from the cache (e.g. after delete or slug change)."""
    _slug_to_id_cache.pop(slug, None)


def clear_slug_to_id_cache() -> None:
    """Clear entire slug-to-id cache."""
    _slug_to_id_cache.clear()
