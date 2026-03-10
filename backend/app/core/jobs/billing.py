"""Billing background jobs."""

import structlog

from app.core.jobs.retry import retry_or_fail
from app.core.metrics import job_completed_total, job_failed_total, job_started_total

logger = structlog.get_logger()

MAX_TRIES = 3


async def generate_invoices_job(
    ctx: dict,
    *,
    tenant_slug: str,
    period_start: str,
    period_end: str,
    correlation_id: str | None = None,
    actor_user_id: str | None = None,
) -> bool:
    """Generate tuition invoices for a tenant. Runs as background job."""
    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="generate_invoices_job").inc()
    logger.info(
        "job.generate_invoices",
        tenant_slug=tenant_slug,
        period_start=period_start,
        period_end=period_end,
        attempt=job_try,
        correlation_id=correlation_id,
    )

    try:
        tenant_db_manager = ctx["tenant_db_manager"]

        async for session in tenant_db_manager.get_session(tenant_slug):
            from app.modules.products.school.billing.service import TuitionBillingService

            service = TuitionBillingService(session)
            invoices = await service.generate_invoices(
                period_start=period_start,
                period_end=period_end,
            )
            await session.commit()
            logger.info(
                "job.generate_invoices.done",
                tenant_slug=tenant_slug,
                invoice_count=len(invoices),
            )

        job_completed_total.labels(job_name="generate_invoices_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="generate_invoices_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="generate_invoices_job",
            tenant_slug=tenant_slug,
        )
        return False


async def send_invoice_email_job(
    ctx: dict,
    *,
    tenant_slug: str,
    invoice_id: str,
    correlation_id: str | None = None,
) -> bool:
    """Send invoice email for a specific invoice."""
    job_try = ctx.get("job_try", 1)
    logger.info(
        "job.send_invoice_email",
        tenant_slug=tenant_slug,
        invoice_id=invoice_id,
        attempt=job_try,
        correlation_id=correlation_id,
    )

    # Placeholder — actual implementation depends on invoice email templates
    logger.warning("job.send_invoice_email.not_implemented")
    return True


async def generate_platform_invoices_job(ctx: dict) -> bool:
    """Monthly cron job (1st, 06:00) — generate platform invoices for previous month."""
    from datetime import datetime, timezone

    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="generate_platform_invoices_job").inc()

    now = datetime.now(timezone.utc)
    # Bill for the previous month (job runs on 1st of current month)
    if now.month == 1:
        period_month, period_year = 12, now.year - 1
    else:
        period_month, period_year = now.month - 1, now.year

    logger.info(
        "job.platform_invoices.start",
        period=f"{period_year}-{period_month:02d}",
        attempt=job_try,
    )

    try:
        central_session_factory = ctx["central_session_factory"]
        arq_pool = ctx.get("arq_pool")

        async with central_session_factory() as session:
            from app.modules.platform.billing.service import BillingService

            service = BillingService(session)
            result = await service.generate_platform_invoices(
                period_year=period_year,
                period_month=period_month,
                arq_pool=arq_pool,
            )
            await session.commit()
            logger.info(
                "job.platform_invoices.done",
                generated=result["generated"],
                skipped=result["skipped"],
            )

        job_completed_total.labels(job_name="generate_platform_invoices_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="generate_platform_invoices_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="generate_platform_invoices_job",
        )
        return False


async def send_dunning_reminders_job(ctx: dict) -> bool:
    """Daily cron job (09:00) — sends payment reminder emails for overdue invoices."""
    from app.config import settings as app_settings

    if not app_settings.billing_dunning_enabled:
        logger.info("job.dunning.disabled")
        return True

    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="send_dunning_reminders_job").inc()
    logger.info("job.dunning.start", attempt=job_try)

    try:
        central_session_factory = ctx["central_session_factory"]
        arq_pool = ctx.get("arq_pool")

        async with central_session_factory() as session:
            from app.modules.platform.finance.service import FinanceService

            service = FinanceService(session)
            sent, skipped = await service.send_dunning_reminders(arq_pool)
            logger.info("job.dunning.done", sent=sent, skipped=skipped)

        job_completed_total.labels(job_name="send_dunning_reminders_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="send_dunning_reminders_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="send_dunning_reminders_job",
        )
        return False
