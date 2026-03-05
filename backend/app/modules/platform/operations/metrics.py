"""Tenant metrics collector — queries individual tenant databases for product metrics.

This is a pure query layer. Timeout handling and error recovery live in the service.
Each method returns a dict; if a tenant DB is unreachable, the service catches the exception
and sets metrics_available=False.
"""

from datetime import date, timedelta

import structlog
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import TenantDatabaseManager
from app.modules.products.school.attendance.models import AttendanceRecord, AttendanceStatus
from app.modules.products.school.billing.models import TuitionInvoice, TuitionInvoiceStatus, TuitionPlan
from app.modules.products.school.schedule.models import LessonSlot
from app.modules.products.school.student.models import Student, TeacherStudentAssignment

logger = structlog.get_logger()


class TenantMetricsCollector:
    """Collects product metrics from individual tenant databases.

    Receives tenant_db_manager as dependency (mockable in tests).
    """

    def __init__(self, db_manager: TenantDatabaseManager):
        self.db_manager = db_manager

    async def _get_session(self, slug: str) -> AsyncSession:
        """Get a session for a tenant database."""
        await self.db_manager.get_engine(slug)  # ensure engine+factory exist
        factory = self.db_manager._session_factories[slug]
        return factory()

    async def collect_counts(self, slug: str) -> dict:
        """Student, teacher, invoice counts — lightweight dashboard metrics."""
        session = await self._get_session(slug)
        try:
            student_count = (await session.execute(
                select(func.count(Student.id)).where(Student.is_active.is_(True))
            )).scalar() or 0

            teacher_count = (await session.execute(
                select(func.count(distinct(TeacherStudentAssignment.user_id)))
            )).scalar() or 0

            active_invoice_count = (await session.execute(
                select(func.count(TuitionInvoice.id)).where(
                    TuitionInvoice.status.in_([
                        TuitionInvoiceStatus.sent,
                        TuitionInvoiceStatus.overdue,
                    ])
                )
            )).scalar() or 0

            return {
                "student_count": student_count,
                "teacher_count": teacher_count,
                "active_invoice_count": active_invoice_count,
            }
        finally:
            await session.close()

    async def collect_attendance(self, slug: str, days: int = 30) -> dict:
        """Present/total counts for attendance rate calculation."""
        session = await self._get_session(slug)
        try:
            since = date.today() - timedelta(days=days)

            total = (await session.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.lesson_date >= since
                )
            )).scalar() or 0

            present = (await session.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.lesson_date >= since,
                    AttendanceRecord.status == AttendanceStatus.present,
                )
            )).scalar() or 0

            return {
                "attendance_total_count": total,
                "attendance_present_count": present,
            }
        finally:
            await session.close()

    async def collect_onboarding(self, slug: str) -> dict:
        """Boolean checks for onboarding tracker + last_step_at."""
        session = await self._get_session(slug)
        try:
            has_students = (await session.execute(
                select(func.count(Student.id)).limit(1)
            )).scalar() or 0 > 0

            has_schedule = (await session.execute(
                select(func.count(LessonSlot.id)).limit(1)
            )).scalar() or 0 > 0

            has_attendance = (await session.execute(
                select(func.count(AttendanceRecord.id)).limit(1)
            )).scalar() or 0 > 0

            has_billing_plan = (await session.execute(
                select(func.count(TuitionPlan.id)).limit(1)
            )).scalar() or 0 > 0

            # Most recent product data creation timestamp
            latest_dates = []
            for model in [Student, LessonSlot, AttendanceRecord, TuitionPlan]:
                dt = (await session.execute(
                    select(func.max(model.created_at))
                )).scalar()
                if dt:
                    latest_dates.append(dt)

            last_step_at = max(latest_dates) if latest_dates else None

            return {
                "has_students": has_students,
                "has_schedule": has_schedule,
                "has_attendance": has_attendance,
                "has_billing_plan": has_billing_plan,
                "last_step_at": last_step_at,
            }
        finally:
            await session.close()

    async def collect_full(self, slug: str) -> dict:
        """Everything for Tenant 360° view — combines all metrics."""
        session = await self._get_session(slug)
        try:
            # Student counts
            student_count = (await session.execute(
                select(func.count(Student.id))
            )).scalar() or 0

            active_student_count = (await session.execute(
                select(func.count(Student.id)).where(Student.is_active.is_(True))
            )).scalar() or 0

            # Teacher count (distinct assigned)
            teacher_count = (await session.execute(
                select(func.count(distinct(TeacherStudentAssignment.user_id)))
            )).scalar() or 0

            # Schedule
            lesson_slot_count = (await session.execute(
                select(func.count(LessonSlot.id)).where(LessonSlot.is_active.is_(True))
            )).scalar() or 0

            # Attendance (last 30 days)
            since = date.today() - timedelta(days=30)
            attendance_total = (await session.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.lesson_date >= since
                )
            )).scalar() or 0

            attendance_present = (await session.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.lesson_date >= since,
                    AttendanceRecord.status == AttendanceStatus.present,
                )
            )).scalar() or 0

            # Invoice stats
            invoice_rows = (await session.execute(
                select(
                    TuitionInvoice.status,
                    func.count(TuitionInvoice.id),
                    func.coalesce(func.sum(TuitionInvoice.total_cents), 0),
                ).group_by(TuitionInvoice.status)
            )).all()

            invoice_stats = {
                "sent_count": 0,
                "paid_count": 0,
                "overdue_count": 0,
                "total_outstanding_cents": 0,
                "total_paid_cents": 0,
            }
            for status, count, total in invoice_rows:
                if status == TuitionInvoiceStatus.sent:
                    invoice_stats["sent_count"] = count
                    invoice_stats["total_outstanding_cents"] += total
                elif status == TuitionInvoiceStatus.overdue:
                    invoice_stats["overdue_count"] = count
                    invoice_stats["total_outstanding_cents"] += total
                elif status == TuitionInvoiceStatus.paid:
                    invoice_stats["paid_count"] = count
                    invoice_stats["total_paid_cents"] = total

            return {
                "student_count": student_count,
                "active_student_count": active_student_count,
                "teacher_count": teacher_count,
                "lesson_slot_count": lesson_slot_count,
                "attendance_total_count": attendance_total,
                "attendance_present_count": attendance_present,
                "invoice_stats": invoice_stats,
            }
        finally:
            await session.close()
