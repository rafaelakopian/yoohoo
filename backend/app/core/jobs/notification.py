"""Notification processing background job."""


import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jobs.retry import retry_or_fail
from app.core.metrics import job_completed_total, job_failed_total, job_started_total
from app.modules.products.school.notification.models import NotificationType
from app.modules.products.school.notification.service import NotificationService
from app.modules.products.school.notification.templates import (
    build_absence_alert_email,
    build_schedule_change_email,
)

logger = structlog.get_logger()

MAX_TRIES = 3


async def process_notification_job(
    ctx: dict,
    *,
    tenant_slug: str,
    event_name: str,
    correlation_id: str | None = None,
    **event_data,
) -> bool:
    """Process notification event as background job."""
    job_try = ctx.get("job_try", 1)
    job_started_total.labels(job_name="process_notification_job").inc()
    logger.info(
        "job.process_notification",
        tenant_slug=tenant_slug,
        event_name=event_name,
        attempt=job_try,
        correlation_id=correlation_id,
    )

    try:
        tenant_db_manager = ctx["tenant_db_manager"]

        async for session in tenant_db_manager.get_session(tenant_slug):
            service = NotificationService(session)

            if event_name == "attendance.created":
                await _handle_attendance(service, session, event_data)
            elif event_name == "schedule.lesson_cancelled":
                await _handle_lesson_cancelled(service, session, event_data)
            elif event_name == "schedule.lesson_rescheduled":
                await _handle_lesson_rescheduled(service, session, event_data)
            else:
                logger.warning("job.unknown_event", event_name=event_name)

        job_completed_total.labels(job_name="process_notification_job").inc()
        return True
    except Exception as exc:
        job_failed_total.labels(job_name="process_notification_job").inc()
        retry_or_fail(
            job_try=job_try,
            max_tries=MAX_TRIES,
            error=exc,
            job_name="process_notification_job",
            tenant_slug=tenant_slug,
            event_name=event_name,
        )
        return False


async def _handle_attendance(
    service: NotificationService, session: AsyncSession, data: dict
) -> None:
    """Handle attendance.created notification."""
    status = data.get("status")
    if status not in ("absent", "sick"):
        return

    guardian_email = data.get("guardian_email")
    student_name = data.get("student_name")
    lesson_date = data.get("lesson_date")
    guardian_name = data.get("guardian_name")

    if not guardian_email or not student_name or not lesson_date:
        logger.debug("job.notification.skip_attendance", reason="missing_data")
        return

    # Check if absence_alert is enabled
    try:
        pref = await service.get_preference(NotificationType.absence_alert)
        if not pref.is_enabled:
            logger.debug("job.notification.skip_attendance", reason="disabled")
            return
    except Exception:
        pass  # No preference set, default to sending

    subject, html = build_absence_alert_email(
        student_name=student_name,
        lesson_date=lesson_date,
        status=status,
    )
    await service.send_notification(
        notification_type=NotificationType.absence_alert,
        recipient_email=guardian_email,
        recipient_name=guardian_name,
        subject=subject,
        html_body=html,
        context_data={
            "student_name": student_name,
            "lesson_date": lesson_date,
            "status": status,
        },
    )
    await session.commit()


async def _handle_lesson_cancelled(
    service: NotificationService, session: AsyncSession, data: dict
) -> None:
    """Handle schedule.lesson_cancelled notification."""
    guardian_email = data.get("guardian_email")
    student_name = data.get("student_name")
    lesson_date = data.get("lesson_date")
    guardian_name = data.get("guardian_name")

    if not guardian_email or not student_name or not lesson_date:
        logger.debug("job.notification.skip_cancel", reason="missing_data")
        return

    subject, html = build_schedule_change_email(
        student_name=student_name,
        original_date=lesson_date,
        new_date="geannuleerd",
        new_time="-",
        reason="Les geannuleerd",
    )
    await service.send_notification(
        notification_type=NotificationType.schedule_change,
        recipient_email=guardian_email,
        recipient_name=guardian_name,
        subject=subject,
        html_body=html,
        context_data={
            "student_name": student_name,
            "lesson_date": lesson_date,
            "action": "cancelled",
        },
    )
    await session.commit()


async def _handle_lesson_rescheduled(
    service: NotificationService, session: AsyncSession, data: dict
) -> None:
    """Handle schedule.lesson_rescheduled notification."""
    guardian_email = data.get("guardian_email")
    student_name = data.get("student_name")
    original_date = data.get("original_date")
    new_date = data.get("new_date")
    new_time = data.get("new_time")
    reason = data.get("reason")
    guardian_name = data.get("guardian_name")

    if not guardian_email or not student_name or not original_date or not new_date or not new_time:
        logger.debug("job.notification.skip_reschedule", reason="missing_data")
        return

    subject, html = build_schedule_change_email(
        student_name=student_name,
        original_date=original_date,
        new_date=new_date,
        new_time=new_time,
        reason=reason,
    )
    await service.send_notification(
        notification_type=NotificationType.schedule_change,
        recipient_email=guardian_email,
        recipient_name=guardian_name,
        subject=subject,
        html_body=html,
        context_data={
            "student_name": student_name,
            "original_date": original_date,
            "new_date": new_date,
            "new_time": new_time,
            "action": "rescheduled",
        },
    )
    await session.commit()
