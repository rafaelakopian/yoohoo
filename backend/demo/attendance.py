"""Demo attendance records for the past 8 weeks."""

import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.attendance.models import AttendanceRecord, AttendanceStatus
from app.modules.products.school.schedule.models import LessonInstance


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# Deterministic pattern (per 20 instances): 17 present, 2 excused, 1 absent
# → 85% present, 10% excused, 5% absent
_STATUS_CYCLE = (
    [AttendanceStatus.present] * 17
    + [AttendanceStatus.excused] * 2
    + [AttendanceStatus.absent] * 1
)


async def create_demo_attendance(
    db: AsyncSession,
    users: dict,
) -> int:
    """Create attendance records for all past lesson instances in this tenant DB."""
    today = date.today()

    result = await db.execute(
        select(LessonInstance).where(LessonInstance.lesson_date < today)
    )
    past_instances = list(result.scalars().all())

    if not past_instances:
        _log("    Geen lessen in het verleden — geen aanwezigheid aangemaakt")
        return 0

    # Use docent1 as recorder
    recorder = users.get("docent1")
    recorder_id = recorder.id if recorder else None
    count = 0

    for i, instance in enumerate(past_instances):
        status = _STATUS_CYCLE[i % len(_STATUS_CYCLE)]
        notes = None
        if status == AttendanceStatus.excused:
            notes = "Vooraf afgemeld"
        elif status == AttendanceStatus.absent:
            notes = "Niet verschenen"

        record = AttendanceRecord(
            student_id=instance.student_id,
            lesson_date=instance.lesson_date,
            status=status,
            recorded_by_user_id=recorder_id,
            notes=notes,
        )
        db.add(record)
        count += 1

    await db.flush()
    _log(f"    {count} aanwezigheidsrecords aangemaakt")
    return count
