import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import event_bus
from app.core.exceptions import NotFoundError
from app.modules.tenant.schedule.models import Holiday, LessonInstance, LessonSlot, LessonStatus
from app.modules.tenant.schedule.schemas import (
    CalendarDayEntry,
    GenerateLessonsRequest,
    GenerateLessonsResponse,
    HolidayCreate,
    HolidayUpdate,
    LessonInstanceCreate,
    LessonInstanceReschedule,
    LessonInstanceUpdate,
    LessonSlotCreate,
    LessonSlotUpdate,
)
from app.modules.tenant.student.models import Student

logger = structlog.get_logger()


class ScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Slot CRUD ───

    async def create_slot(self, data: LessonSlotCreate) -> LessonSlot:
        slot = LessonSlot(**data.model_dump())
        self.db.add(slot)
        await self.db.flush()

        logger.info("schedule.slot_created", slot_id=str(slot.id), student_id=str(slot.student_id))
        await event_bus.emit("schedule.slot_created", slot_id=slot.id)

        return slot

    async def list_slots(
        self,
        page: int = 1,
        per_page: int = 25,
        student_id: uuid.UUID | None = None,
        day_of_week: int | None = None,
        active_only: bool = True,
        teacher_user_id: uuid.UUID | None = None,
        student_ids: list[uuid.UUID] | None = None,
    ) -> tuple[list[LessonSlot], int]:
        query = select(LessonSlot)

        if student_id:
            query = query.where(LessonSlot.student_id == student_id)
        if day_of_week is not None:
            query = query.where(LessonSlot.day_of_week == day_of_week)
        if active_only:
            query = query.where(LessonSlot.is_active.is_(True))
        if teacher_user_id:
            query = query.where(LessonSlot.teacher_user_id == teacher_user_id)
        if student_ids is not None:
            query = query.where(LessonSlot.student_id.in_(student_ids))

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(LessonSlot.day_of_week, LessonSlot.start_time)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        slots = list(result.scalars().all())

        return slots, total

    async def get_slot(self, slot_id: uuid.UUID) -> LessonSlot:
        result = await self.db.execute(
            select(LessonSlot).where(LessonSlot.id == slot_id)
        )
        slot = result.scalar_one_or_none()
        if not slot:
            raise NotFoundError("LessonSlot", str(slot_id))
        return slot

    async def update_slot(self, slot_id: uuid.UUID, data: LessonSlotUpdate) -> LessonSlot:
        slot = await self.get_slot(slot_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(slot, key, value)

        await self.db.flush()
        await self.db.refresh(slot)

        logger.info("schedule.slot_updated", slot_id=str(slot.id))
        await event_bus.emit("schedule.slot_updated", slot_id=slot.id)

        return slot

    async def delete_slot(self, slot_id: uuid.UUID) -> LessonSlot:
        slot = await self.get_slot(slot_id)
        await self.db.delete(slot)
        await self.db.flush()

        logger.info("schedule.slot_deleted", slot_id=str(slot_id))
        await event_bus.emit("schedule.slot_deleted", slot_id=slot_id)

        return slot

    # ─── Instance CRUD ───

    async def create_instance(self, data: LessonInstanceCreate) -> LessonInstance:
        instance = LessonInstance(**data.model_dump())
        self.db.add(instance)
        await self.db.flush()

        logger.info(
            "schedule.instance_created",
            instance_id=str(instance.id),
            student_id=str(instance.student_id),
            date=str(instance.lesson_date),
        )
        await event_bus.emit("schedule.instance_created", instance_id=instance.id)

        return instance

    async def list_instances(
        self,
        page: int = 1,
        per_page: int = 25,
        student_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status: LessonStatus | None = None,
        teacher_user_id: uuid.UUID | None = None,
        student_ids: list[uuid.UUID] | None = None,
    ) -> tuple[list[LessonInstance], int]:
        query = select(LessonInstance)

        if student_id:
            query = query.where(LessonInstance.student_id == student_id)
        if date_from:
            query = query.where(LessonInstance.lesson_date >= date_from)
        if date_to:
            query = query.where(LessonInstance.lesson_date <= date_to)
        if status:
            query = query.where(LessonInstance.status == status)
        if teacher_user_id:
            query = query.where(LessonInstance.teacher_user_id == teacher_user_id)
        if student_ids is not None:
            query = query.where(LessonInstance.student_id.in_(student_ids))

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(LessonInstance.lesson_date, LessonInstance.start_time)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        instances = list(result.scalars().all())

        return instances, total

    async def get_instance(self, instance_id: uuid.UUID) -> LessonInstance:
        result = await self.db.execute(
            select(LessonInstance).where(LessonInstance.id == instance_id)
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("LessonInstance", str(instance_id))
        return instance

    async def update_instance(
        self, instance_id: uuid.UUID, data: LessonInstanceUpdate
    ) -> LessonInstance:
        instance = await self.get_instance(instance_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(instance, key, value)

        await self.db.flush()
        await self.db.refresh(instance)

        logger.info("schedule.instance_updated", instance_id=str(instance.id))
        await event_bus.emit("schedule.instance_updated", instance_id=instance.id)

        return instance

    async def cancel_instance(
        self, instance_id: uuid.UUID, reason: str | None = None
    ) -> LessonInstance:
        instance = await self.get_instance(instance_id)
        instance.status = LessonStatus.cancelled
        instance.cancellation_reason = reason

        await self.db.flush()
        await self.db.refresh(instance)

        logger.info("schedule.instance_cancelled", instance_id=str(instance.id))
        await event_bus.emit(
            "schedule.lesson_cancelled",
            instance_id=instance.id,
            student_id=instance.student_id,
        )

        return instance

    async def reschedule_instance(
        self, instance_id: uuid.UUID, data: LessonInstanceReschedule
    ) -> LessonInstance:
        original = await self.get_instance(instance_id)

        # Mark original as rescheduled
        original.status = LessonStatus.rescheduled
        original.rescheduled_to_date = data.new_date
        original.rescheduled_to_time = data.new_time
        if data.reason:
            original.cancellation_reason = data.reason

        # Create the new instance
        new_instance = LessonInstance(
            lesson_slot_id=original.lesson_slot_id,
            student_id=original.student_id,
            lesson_date=data.new_date,
            start_time=data.new_time,
            duration_minutes=original.duration_minutes,
            status=LessonStatus.scheduled,
            teacher_user_id=original.teacher_user_id,
        )
        self.db.add(new_instance)
        await self.db.flush()
        await self.db.refresh(original)

        logger.info(
            "schedule.instance_rescheduled",
            original_id=str(instance_id),
            new_id=str(new_instance.id),
        )
        await event_bus.emit(
            "schedule.lesson_rescheduled",
            original_id=instance_id,
            new_id=new_instance.id,
            student_id=original.student_id,
        )

        return new_instance

    # ─── Generate Instances ───

    async def generate_instances(
        self, data: GenerateLessonsRequest
    ) -> GenerateLessonsResponse:
        generated = 0
        skipped = 0
        errors: list[str] = []

        # Load active slots
        result = await self.db.execute(
            select(LessonSlot).where(LessonSlot.is_active.is_(True))
        )
        slots = list(result.scalars().all())

        if not slots:
            return GenerateLessonsResponse(generated=0, skipped=0, errors=[])

        # Load holidays in range
        holidays_result = await self.db.execute(
            select(Holiday).where(
                Holiday.start_date <= data.end_date,
                Holiday.end_date >= data.start_date,
            )
        )
        holidays = list(holidays_result.scalars().all())

        # Build set of holiday dates
        holiday_dates: set[date] = set()
        for h in holidays:
            d = max(h.start_date, data.start_date)
            while d <= min(h.end_date, data.end_date):
                holiday_dates.add(d)
                d += timedelta(days=1)

        # Load existing instances in range to avoid duplicates
        existing_result = await self.db.execute(
            select(LessonInstance.student_id, LessonInstance.lesson_date).where(
                LessonInstance.lesson_date >= data.start_date,
                LessonInstance.lesson_date <= data.end_date,
            )
        )
        existing_pairs: set[tuple[uuid.UUID, date]] = {
            (row.student_id, row.lesson_date) for row in existing_result.all()
        }

        # Generate instances
        current = data.start_date
        while current <= data.end_date:
            # isoweekday: 1=Monday, 7=Sunday
            weekday = current.isoweekday()

            for slot in slots:
                if slot.day_of_week != weekday:
                    continue

                if current in holiday_dates:
                    skipped += 1
                    continue

                if (slot.student_id, current) in existing_pairs:
                    skipped += 1
                    continue

                try:
                    instance = LessonInstance(
                        lesson_slot_id=slot.id,
                        student_id=slot.student_id,
                        lesson_date=current,
                        start_time=slot.start_time,
                        duration_minutes=slot.duration_minutes,
                        status=LessonStatus.scheduled,
                        teacher_user_id=slot.teacher_user_id,
                    )
                    self.db.add(instance)
                    existing_pairs.add((slot.student_id, current))
                    generated += 1
                except Exception as e:
                    errors.append(f"{current} slot {slot.id}: {e}")

            current += timedelta(days=1)

        if generated > 0:
            await self.db.flush()

        logger.info(
            "schedule.lessons_generated",
            start=str(data.start_date),
            end=str(data.end_date),
            generated=generated,
            skipped=skipped,
        )
        await event_bus.emit(
            "schedule.lessons_generated",
            start_date=str(data.start_date),
            end_date=str(data.end_date),
            generated=generated,
        )

        return GenerateLessonsResponse(
            generated=generated, skipped=skipped, errors=errors
        )

    # ─── Substitution ───

    async def assign_substitute(
        self,
        instance_id: uuid.UUID,
        substitute_teacher_user_id: uuid.UUID,
        reason: str | None = None,
    ) -> LessonInstance:
        instance = await self.get_instance(instance_id)
        instance.substitute_teacher_user_id = substitute_teacher_user_id
        instance.substitution_reason = reason

        await self.db.flush()
        await self.db.refresh(instance)

        logger.info(
            "schedule.substitute_assigned",
            instance_id=str(instance.id),
            substitute_teacher=str(substitute_teacher_user_id),
        )
        await event_bus.emit(
            "schedule.substitute_assigned",
            instance_id=instance.id,
            teacher_user_id=instance.teacher_user_id,
            substitute_teacher_user_id=substitute_teacher_user_id,
            student_id=instance.student_id,
        )

        return instance

    # ─── Holiday CRUD ───

    async def create_holiday(self, data: HolidayCreate) -> Holiday:
        holiday = Holiday(**data.model_dump())
        self.db.add(holiday)
        await self.db.flush()

        logger.info("schedule.holiday_created", holiday_id=str(holiday.id))
        await event_bus.emit("schedule.holiday_created", holiday_id=holiday.id)

        return holiday

    async def list_holidays(
        self, page: int = 1, per_page: int = 25
    ) -> tuple[list[Holiday], int]:
        query = select(Holiday)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Holiday.start_date)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        holidays = list(result.scalars().all())

        return holidays, total

    async def get_holiday(self, holiday_id: uuid.UUID) -> Holiday:
        result = await self.db.execute(
            select(Holiday).where(Holiday.id == holiday_id)
        )
        holiday = result.scalar_one_or_none()
        if not holiday:
            raise NotFoundError("Holiday", str(holiday_id))
        return holiday

    async def update_holiday(
        self, holiday_id: uuid.UUID, data: HolidayUpdate
    ) -> Holiday:
        holiday = await self.get_holiday(holiday_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(holiday, key, value)

        await self.db.flush()
        await self.db.refresh(holiday)

        logger.info("schedule.holiday_updated", holiday_id=str(holiday.id))
        return holiday

    async def delete_holiday(self, holiday_id: uuid.UUID) -> Holiday:
        holiday = await self.get_holiday(holiday_id)
        await self.db.delete(holiday)
        await self.db.flush()

        logger.info("schedule.holiday_deleted", holiday_id=str(holiday_id))
        return holiday

    # ─── Calendar ───

    async def get_calendar_week(
        self,
        week_start: date,
        teacher_user_id: uuid.UUID | None = None,
        student_ids: list[uuid.UUID] | None = None,
    ) -> dict:
        week_end = week_start + timedelta(days=6)

        # Get lessons with student names
        query = (
            select(LessonInstance, Student.first_name, Student.last_name)
            .join(Student, LessonInstance.student_id == Student.id)
            .where(
                LessonInstance.lesson_date >= week_start,
                LessonInstance.lesson_date <= week_end,
            )
        )

        if teacher_user_id:
            query = query.where(LessonInstance.teacher_user_id == teacher_user_id)
        if student_ids is not None:
            query = query.where(LessonInstance.student_id.in_(student_ids))

        query = query.order_by(LessonInstance.lesson_date, LessonInstance.start_time)
        lesson_result = await self.db.execute(query)

        lessons = []
        for row in lesson_result.all():
            instance = row[0]
            first = row[1] or ""
            last = row[2] or ""
            name = f"{first} {last}".strip()
            lessons.append(
                CalendarDayEntry(
                    id=instance.id,
                    student_name=name,
                    lesson_date=instance.lesson_date,
                    start_time=instance.start_time,
                    duration_minutes=instance.duration_minutes,
                    status=instance.status,
                    teacher_user_id=instance.teacher_user_id,
                    substitute_teacher_user_id=instance.substitute_teacher_user_id,
                )
            )

        # Get holidays overlapping the week
        holidays_result = await self.db.execute(
            select(Holiday).where(
                Holiday.start_date <= week_end,
                Holiday.end_date >= week_start,
            )
        )
        holidays = list(holidays_result.scalars().all())

        return {
            "week_start": week_start,
            "week_end": week_end,
            "lessons": lessons,
            "holidays": holidays,
        }
