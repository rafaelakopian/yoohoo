from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import event_bus
from app.core.exceptions import NotFoundError
from app.modules.products.school.attendance.models import AttendanceRecord
from app.modules.products.school.attendance.schemas import (
    AttendanceBulkCreate,
    AttendanceBulkResponse,
    AttendanceCreate,
    AttendanceUpdate,
)

logger = structlog.get_logger()


class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: AttendanceCreate) -> AttendanceRecord:
        record = AttendanceRecord(**data.model_dump())
        self.db.add(record)
        await self.db.flush()

        logger.info(
            "attendance.created",
            record_id=str(record.id),
            student_id=str(record.student_id),
            date=str(record.lesson_date),
        )
        await event_bus.emit("attendance.created", record_id=record.id)

        return record

    async def bulk_create(
        self,
        data: AttendanceBulkCreate,
        recorded_by_user_id: uuid.UUID | None = None,
    ) -> AttendanceBulkResponse:
        created = 0
        updated = 0
        errors: list[str] = []

        for i, item in enumerate(data.records, start=1):
            try:
                # Check if record already exists for this student+date
                result = await self.db.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.student_id == item.student_id,
                        AttendanceRecord.lesson_date == data.lesson_date,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.status = item.status
                    if item.notes is not None:
                        existing.notes = item.notes
                    if recorded_by_user_id:
                        existing.recorded_by_user_id = recorded_by_user_id
                    updated += 1
                else:
                    record = AttendanceRecord(
                        student_id=item.student_id,
                        lesson_date=data.lesson_date,
                        status=item.status,
                        notes=item.notes,
                        recorded_by_user_id=recorded_by_user_id,
                    )
                    self.db.add(record)
                    created += 1
            except Exception:
                logger.warning("attendance.bulk_record_error", record=i, exc_info=True)
                errors.append(f"Record {i}: Kon niet worden verwerkt")

        if created > 0 or updated > 0:
            await self.db.flush()
            logger.info(
                "attendance.bulk_created",
                date=str(data.lesson_date),
                created=created,
                updated=updated,
            )
            await event_bus.emit(
                "attendance.bulk_created",
                date=str(data.lesson_date),
                created=created,
                updated=updated,
            )

        return AttendanceBulkResponse(created=created, updated=updated, errors=errors)

    async def list(
        self,
        page: int = 1,
        per_page: int = 25,
        student_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[AttendanceRecord], int]:
        query = select(AttendanceRecord)

        if student_id:
            query = query.where(AttendanceRecord.student_id == student_id)
        if date_from:
            query = query.where(AttendanceRecord.lesson_date >= date_from)
        if date_to:
            query = query.where(AttendanceRecord.lesson_date <= date_to)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(AttendanceRecord.lesson_date.desc(), AttendanceRecord.created_at)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        records = list(result.scalars().all())

        return records, total

    async def list_for_students(
        self,
        student_ids: list[uuid.UUID],
        page: int = 1,
        per_page: int = 25,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[AttendanceRecord], int]:
        """List attendance records for a specific set of students (used for parent filtering)."""
        query = select(AttendanceRecord).where(
            AttendanceRecord.student_id.in_(student_ids)
        )

        if date_from:
            query = query.where(AttendanceRecord.lesson_date >= date_from)
        if date_to:
            query = query.where(AttendanceRecord.lesson_date <= date_to)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(AttendanceRecord.lesson_date.desc(), AttendanceRecord.created_at)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        records = list(result.scalars().all())
        return records, total

    async def get(self, record_id: uuid.UUID) -> AttendanceRecord:
        result = await self.db.execute(
            select(AttendanceRecord).where(AttendanceRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise NotFoundError("AttendanceRecord", str(record_id))
        return record

    async def update(self, record_id: uuid.UUID, data: AttendanceUpdate) -> AttendanceRecord:
        record = await self.get(record_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(record, key, value)

        await self.db.flush()
        await self.db.refresh(record)

        logger.info("attendance.updated", record_id=str(record.id))
        await event_bus.emit("attendance.updated", record_id=record.id)

        return record

    async def delete(self, record_id: uuid.UUID) -> AttendanceRecord:
        record = await self.get(record_id)
        await self.db.delete(record)
        await self.db.flush()

        logger.info("attendance.deleted", record_id=str(record_id))
        await event_bus.emit("attendance.deleted", record_id=record_id)

        return record
