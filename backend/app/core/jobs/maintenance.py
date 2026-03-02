"""Maintenance and cleanup background jobs."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def cleanup_unverified_users_job(ctx: dict) -> bool:
    """Periodic cleanup of unverified users older than configured threshold."""
    logger.info("job.cleanup_unverified_users")

    session_factory = ctx["central_session_factory"]
    async with session_factory() as session:
        from app.modules.platform.auth.core.service import cleanup_unverified_users

        count = await cleanup_unverified_users(session)
        logger.info("job.cleanup_unverified_users.done", cleaned=count)

    return True
