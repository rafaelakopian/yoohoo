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
from app.core.jobs.billing import generate_invoices_job, send_invoice_email_job
from app.core.jobs.maintenance import cleanup_unverified_users_job

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

    logger.info("worker.started")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown: close DB connections."""
    logger.info("worker.shutting_down")
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
        func(send_invoice_email_job, max_tries=4),
        func(cleanup_unverified_users_job, max_tries=1),
    ]

    cron_jobs = [
        cron(cleanup_unverified_users_job, hour=3, minute=0),  # 03:00 daily
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
