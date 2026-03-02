"""Event handlers for notifications.

These handlers are subscribed to the event bus. When an arq pool is available,
they enqueue background jobs for reliable processing with retries.
When arq is unavailable, they fall back to direct processing.
"""

import uuid

import structlog
from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.modules.tenant.notification.models import NotificationStatus, NotificationType
from app.modules.tenant.notification.service import NotificationService
from app.modules.tenant.notification.templates import (
    build_absence_alert_email,
    build_schedule_change_email,
)

logger = structlog.get_logger()

# Module-level arq pool reference, set by init_handlers()
_arq_pool: ArqRedis | None = None


def init_handlers(arq_pool: ArqRedis | None) -> None:
    """Initialize handlers with arq pool for background job enqueueing."""
    global _arq_pool
    _arq_pool = arq_pool
    if _arq_pool:
        logger.info("notification.handlers.arq_enabled")
    else:
        logger.warning("notification.handlers.arq_disabled", msg="Falling back to direct processing")


async def _get_tenant_session(tenant_slug: str) -> async_sessionmaker[AsyncSession]:
    """Create a session factory for the given tenant (fallback mode only)."""
    url = settings.tenant_database_url(tenant_slug)
    engine = create_async_engine(url, pool_size=2, max_overflow=0)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def on_attendance_created(
    record_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    status: str | None = None,
    student_name: str | None = None,
    lesson_date: str | None = None,
    guardian_email: str | None = None,
    guardian_name: str | None = None,
    tenant_slug: str | None = None,
    **kwargs,
) -> None:
    """Send absence alert when attendance is absent/sick."""
    if status not in ("absent", "sick"):
        return

    if not tenant_slug or not guardian_email or not student_name or not lesson_date:
        logger.debug(
            "notification.skip_attendance",
            reason="missing_data",
            record_id=str(record_id),
        )
        return

    # Enqueue as arq job if available
    if _arq_pool:
        await _arq_pool.enqueue_job(
            "process_notification_job",
            tenant_slug=tenant_slug,
            event_name="attendance.created",
            status=status,
            student_name=student_name,
            lesson_date=lesson_date,
            guardian_email=guardian_email,
            guardian_name=guardian_name,
        )
        logger.debug("notification.enqueued", event="attendance.created", tenant=tenant_slug)
        return

    # Fallback: direct processing (no arq available)
    try:
        session_factory = await _get_tenant_session(tenant_slug)
        async with session_factory() as session:
            service = NotificationService(session)

            try:
                pref = await service.get_preference(NotificationType.absence_alert)
                if not pref.is_enabled:
                    logger.debug("notification.skip_attendance", reason="disabled")
                    return
            except Exception:
                pass

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
    except Exception:
        logger.exception("notification.handler_error", handler="on_attendance_created")


async def on_lesson_cancelled(
    instance_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    student_name: str | None = None,
    lesson_date: str | None = None,
    guardian_email: str | None = None,
    guardian_name: str | None = None,
    tenant_slug: str | None = None,
    **kwargs,
) -> None:
    """Send cancellation notification when a lesson is cancelled."""
    if not tenant_slug or not guardian_email or not student_name or not lesson_date:
        logger.debug(
            "notification.skip_cancel",
            reason="missing_data",
            instance_id=str(instance_id),
        )
        return

    # Enqueue as arq job if available
    if _arq_pool:
        await _arq_pool.enqueue_job(
            "process_notification_job",
            tenant_slug=tenant_slug,
            event_name="schedule.lesson_cancelled",
            student_name=student_name,
            lesson_date=lesson_date,
            guardian_email=guardian_email,
            guardian_name=guardian_name,
        )
        logger.debug("notification.enqueued", event="schedule.lesson_cancelled", tenant=tenant_slug)
        return

    # Fallback: direct processing
    try:
        session_factory = await _get_tenant_session(tenant_slug)
        async with session_factory() as session:
            service = NotificationService(session)

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
    except Exception:
        logger.exception("notification.handler_error", handler="on_lesson_cancelled")


async def on_lesson_rescheduled(
    original_id: uuid.UUID,
    new_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    student_name: str | None = None,
    original_date: str | None = None,
    new_date: str | None = None,
    new_time: str | None = None,
    reason: str | None = None,
    guardian_email: str | None = None,
    guardian_name: str | None = None,
    tenant_slug: str | None = None,
    **kwargs,
) -> None:
    """Send reschedule notification."""
    if (
        not tenant_slug
        or not guardian_email
        or not student_name
        or not original_date
        or not new_date
        or not new_time
    ):
        logger.debug(
            "notification.skip_reschedule",
            reason="missing_data",
            original_id=str(original_id),
        )
        return

    # Enqueue as arq job if available
    if _arq_pool:
        await _arq_pool.enqueue_job(
            "process_notification_job",
            tenant_slug=tenant_slug,
            event_name="schedule.lesson_rescheduled",
            student_name=student_name,
            original_date=original_date,
            new_date=new_date,
            new_time=new_time,
            reason=reason,
            guardian_email=guardian_email,
            guardian_name=guardian_name,
        )
        logger.debug("notification.enqueued", event="schedule.lesson_rescheduled", tenant=tenant_slug)
        return

    # Fallback: direct processing
    try:
        session_factory = await _get_tenant_session(tenant_slug)
        async with session_factory() as session:
            service = NotificationService(session)

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
    except Exception:
        logger.exception("notification.handler_error", handler="on_lesson_rescheduled")
