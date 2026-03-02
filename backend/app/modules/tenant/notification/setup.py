"""Register notification event handlers on the event bus."""

import structlog
from arq import ArqRedis

from app.core.event_bus import event_bus
from app.modules.tenant.notification.handlers import (
    init_handlers,
    on_attendance_created,
    on_lesson_cancelled,
    on_lesson_rescheduled,
)

logger = structlog.get_logger()


def register_notification_handlers(arq_pool: ArqRedis | None = None) -> None:
    """Subscribe notification handlers to relevant events."""
    # Initialize handlers with arq pool for background job enqueueing
    init_handlers(arq_pool)

    event_bus.subscribe("attendance.created", on_attendance_created)
    event_bus.subscribe("schedule.lesson_cancelled", on_lesson_cancelled)
    event_bus.subscribe("schedule.lesson_rescheduled", on_lesson_rescheduled)
    logger.info("notification.handlers_registered", arq_enabled=arq_pool is not None)
