"""Maintenance and cleanup background jobs."""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update as sa_update

from app.config import settings

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


async def anonymize_archived_accounts_job(ctx: dict) -> bool:
    """Anonymize archived accounts whose retention period has expired."""
    if not settings.data_retention_auto_anonymize:
        logger.info("job.anonymize_archived.skipped", reason="auto_anonymize disabled")
        return True

    logger.info("job.anonymize_archived.start")

    session_factory = ctx["central_session_factory"]
    async with session_factory() as session:
        from app.modules.platform.auth.models import User

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.data_retention_account_archive_days
        )

        # Find archived accounts past the retention window
        result = await session.execute(
            select(User).where(
                User.archived_at != None,  # noqa: E711
                User.archived_at <= cutoff,
                User.anonymized_at == None,  # noqa: E711
            )
        )
        users = result.scalars().all()

        if not users:
            logger.info("job.anonymize_archived.done", count=0)
            return True

        now = datetime.now(timezone.utc)
        count = 0
        for user in users:
            # Anonymize PII
            user.email = f"anonymized-{user.id}@deleted.local"
            user.full_name = "Geanonimiseerd"
            user.hashed_password = "ANONYMIZED"
            user.phone_number = None
            user.totp_secret_encrypted = None
            user.totp_enabled = False
            user.pending_email = None
            user.pending_email_token_hash = None
            user.verification_token_hash = None
            user.anonymized_at = now
            count += 1

        await session.commit()
        logger.info("job.anonymize_archived.done", count=count)

    return True
