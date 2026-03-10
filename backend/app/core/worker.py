"""arq worker configuration.

Start with: arq app.core.worker.WorkerSettings
"""

import structlog
from arq import cron, func
from arq.connections import RedisSettings

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.jobs.email import send_email_job
from app.core.jobs.notification import process_notification_job
from app.core.jobs.billing import generate_invoices_job, generate_platform_invoices_job, send_dunning_reminders_job, send_invoice_email_job
from app.core.jobs.feature_trials import expire_trials_job, purge_expired_retention_job
from app.core.jobs.maintenance import cleanup_unverified_users_job, anonymize_archived_accounts_job

logger = structlog.get_logger()


async def startup(ctx: dict) -> None:
    """Worker startup: init DB connections + logging."""
    setup_logging()
    logger.info("worker.starting")

    from app.db.central import async_session_factory
    from app.db.tenant import tenant_db_manager

    ctx["settings"] = settings
    ctx["tenant_db_manager"] = tenant_db_manager
    ctx["central_session_factory"] = async_session_factory

    # Initialize email providers (fail-fast on misconfig, not on connectivity)
    from app.core.email import _get_providers
    try:
        _get_providers()
    except ValueError as e:
        raise RuntimeError(f"FATAL: email provider misconfiguration: {e}") from e

    logger.info("worker.started")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown: close DB connections + email providers."""
    logger.info("worker.shutting_down")
    from app.core.email import close_providers
    await close_providers()
    tenant_db_manager = ctx.get("tenant_db_manager")
    if tenant_db_manager:
        await tenant_db_manager.close_all()
    logger.info("worker.stopped")


class WorkerSettings:
    """arq worker configuration."""

    functions = [
        func(send_email_job, max_tries=4),
        func(process_notification_job, max_tries=3),
        func(generate_invoices_job, max_tries=3),
        func(generate_platform_invoices_job, max_tries=3),
        func(send_invoice_email_job, max_tries=4),
        func(cleanup_unverified_users_job, max_tries=1),
        func(anonymize_archived_accounts_job, max_tries=1),
        func(send_dunning_reminders_job, max_tries=1),
        func(expire_trials_job, max_tries=3),
        func(purge_expired_retention_job, max_tries=3),
    ]

    cron_jobs = [
        cron(cleanup_unverified_users_job, hour=3, minute=0),  # 03:00 daily
        cron(anonymize_archived_accounts_job, hour=4, minute=0),  # 04:00 daily
        cron(generate_platform_invoices_job, hour=6, minute=0, day=1),  # 1st of month, 06:00
        cron(send_dunning_reminders_job, hour=9, minute=0),  # 09:00 daily
        cron(expire_trials_job, hour=2, minute=0),  # 02:00 daily
        cron(purge_expired_retention_job, hour=2, minute=30),  # 02:30 daily
    ]

    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.arq_redis_db,
    )

    max_jobs = settings.arq_max_jobs
    job_timeout = settings.arq_job_timeout
