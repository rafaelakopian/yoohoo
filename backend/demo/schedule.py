"""Demo schedule: lesson slots and instance generation."""

import sys
from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.school.schedule.models import LessonSlot
from app.modules.products.school.schedule.schemas import GenerateLessonsRequest
from app.modules.products.school.schedule.service import ScheduleService
from app.modules.products.school.student.models import Student


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# Lesson times to cycle through (morning + afternoon)
_TIMES = [
    time(9, 0), time(9, 45), time(10, 30), time(11, 15),
    time(14, 0), time(14, 45), time(15, 30), time(16, 15),
]


async def create_demo_schedule(
    db: AsyncSession,
    students: list[Student],
    users: dict,
) -> list[LessonSlot]:
    """Create one lesson slot per student and generate instances for 8 weeks back + 4 weeks forward."""
    slots: list[LessonSlot] = []

    for i, student in enumerate(students):
        day_of_week = (i % 5) + 1  # 1=ma .. 5=vr
        start_time = _TIMES[i % len(_TIMES)]
        duration = student.lesson_duration or 30

        # Assign teacher from the TeacherStudentAssignment — use the pattern from student defs
        # docent1 gets first half, docent2 gets second half
        teacher_key = "docent1" if i < len(students) // 2 else "docent2"
        teacher_user = users.get(teacher_key)

        slot = LessonSlot(
            student_id=student.id,
            day_of_week=day_of_week,
            start_time=start_time,
            duration_minutes=duration,
            teacher_user_id=teacher_user.id if teacher_user else None,
            is_active=True,
        )
        db.add(slot)
        slots.append(slot)

    await db.flush()
    _log(f"    {len(slots)} lesslots aangemaakt")

    # Generate instances: 8 weeks back + 4 weeks forward
    today = date.today()
    svc = ScheduleService(db)
    result = await svc.generate_instances(GenerateLessonsRequest(
        start_date=today - timedelta(weeks=8),
        end_date=today + timedelta(weeks=4),
    ))
    await db.flush()
    _log(f"    {result.generated} lessen gegenereerd ({result.skipped} overgeslagen)")

    return slots
