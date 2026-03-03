from collections.abc import AsyncGenerator

import redis.asyncio as redis
from arq import ArqRedis
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import tenant_db_manager


async def get_redis(request: Request) -> redis.Redis | None:
    """Get Redis connection from app state, or None if unavailable."""
    return getattr(request.app.state, "redis", None)


async def get_arq(request: Request) -> ArqRedis | None:
    """Get arq Redis pool for enqueueing background jobs."""
    return getattr(request.app.state, "arq", None)


async def get_tenant_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for the current tenant."""
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if not tenant_slug:
        from app.core.exceptions import AppException
        raise AppException("No tenant context available", status_code=400)

    async for session in tenant_db_manager.get_session(tenant_slug):
        yield session
