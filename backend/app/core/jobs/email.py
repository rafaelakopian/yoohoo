"""Email sending background job."""

import structlog

from app.core.email import send_email_safe
from app.core.jobs.retry import retry_or_fail
from app.core.metrics import job_completed_total, job_failed_total, job_started_total

logger = structlog.get_logger()

MAX_TRIES = 4


async def send_email_job(
    ctx: dict,
    *,
    to: str,
    subject: str,
    html_body: str,
    correlation_id: str | None = None,
) -> bool:
    """Send email via SMTP with exponential backoff retry."""
    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="send_email_job").inc()
    logger.info("job.send_email", to=to, subject=subject, attempt=job_try, correlation_id=correlation_id)

    try:
        success = await send_email_safe(to, subject, html_body)
        if not success:
            raise Exception(f"Email delivery failed: {to}")
        job_completed_total.labels(job_name="send_email_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="send_email_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="send_email_job",
            to=to,
            subject=subject,
        )
        return False
