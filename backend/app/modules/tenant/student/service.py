import uuid

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import event_bus
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.tenant.student.models import ParentStudentLink, Student, TeacherStudentAssignment
from app.modules.tenant.student.schemas import StudentCreate, StudentImportResponse, StudentUpdate

logger = structlog.get_logger()


class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_student(self, data: StudentCreate) -> Student:
        student = Student(**data.model_dump())
        self.db.add(student)
        await self.db.flush()

        logger.info("student.created", student_id=str(student.id), name=student.first_name)
        await event_bus.emit("student.created", student_id=student.id)

        return student

    async def list_students(
        self,
        page: int = 1,
        per_page: int = 25,
        search: str | None = None,
        active_only: bool = True,
        parent_user_id: uuid.UUID | None = None,
        teacher_user_id: uuid.UUID | None = None,
    ) -> tuple[list[Student], int]:
        query = select(Student)

        if active_only:
            query = query.where(Student.is_active)

        # Parent filtering: only show linked children
        if parent_user_id:
            linked_ids = await self.get_linked_student_ids(parent_user_id)
            if not linked_ids:
                return [], 0
            query = query.where(Student.id.in_(linked_ids))

        # Teacher filtering: only show assigned students
        if teacher_user_id:
            assigned_ids = await self.get_assigned_student_ids(teacher_user_id)
            if not assigned_ids:
                return [], 0
            query = query.where(Student.id.in_(assigned_ids))

        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_term = f"%{escaped}%"
            query = query.where(
                or_(
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                    Student.email.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(Student.first_name, Student.last_name)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        students = list(result.scalars().all())

        return students, total

    async def get_student(
        self,
        student_id: uuid.UUID,
        parent_user_id: uuid.UUID | None = None,
        teacher_user_id: uuid.UUID | None = None,
    ) -> Student:
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                Student.is_active,
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError("Student", str(student_id))

        # If parent_user_id is set, verify the parent is linked to this student
        if parent_user_id:
            linked_ids = await self.get_linked_student_ids(parent_user_id)
            if student.id not in linked_ids:
                raise ForbiddenError("You do not have access to this student")

        # If teacher_user_id is set, verify the teacher is assigned to this student
        if teacher_user_id:
            assigned_ids = await self.get_assigned_student_ids(teacher_user_id)
            if student.id not in assigned_ids:
                raise ForbiddenError("You do not have access to this student")

        return student

    async def update_student(self, student_id: uuid.UUID, data: StudentUpdate) -> Student:
        student = await self.get_student(student_id)
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(student, key, value)

        await self.db.flush()
        await self.db.refresh(student)

        logger.info("student.updated", student_id=str(student.id))
        await event_bus.emit("student.updated", student_id=student.id)

        return student

    async def delete_student(self, student_id: uuid.UUID) -> Student:
        student = await self.get_student(student_id)
        student.is_active = False
        await self.db.flush()
        await self.db.refresh(student)

        logger.info("student.deleted", student_id=str(student.id))
        await event_bus.emit("student.deleted", student_id=student.id)

        return student

    async def bulk_import(self, students: list[StudentCreate]) -> StudentImportResponse:
        imported = 0
        skipped = 0
        errors: list[str] = []

        for i, data in enumerate(students, start=1):
            try:
                student = Student(**data.model_dump())
                self.db.add(student)
                imported += 1
            except Exception:
                logger.warning("student.bulk_import_row_error", row=i, exc_info=True)
                errors.append(f"Rij {i}: Kon niet worden geïmporteerd")
                skipped += 1

        if imported > 0:
            await self.db.flush()
            logger.info("student.bulk_imported", count=imported, skipped=skipped)
            await event_bus.emit("student.bulk_imported", count=imported)

        return StudentImportResponse(imported=imported, skipped=skipped, errors=errors)

    # --- Parent-Student Link operations ---

    async def get_linked_student_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Get all student IDs linked to a parent user."""
        result = await self.db.execute(
            select(ParentStudentLink.student_id).where(
                ParentStudentLink.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def get_linked_parents(self, student_id: uuid.UUID) -> list[ParentStudentLink]:
        """Get all parent links for a student."""
        result = await self.db.execute(
            select(ParentStudentLink).where(
                ParentStudentLink.student_id == student_id
            )
        )
        return list(result.scalars().all())

    async def link_parent(
        self,
        user_id: uuid.UUID,
        student_id: uuid.UUID,
        relationship_type: str = "parent",
    ) -> ParentStudentLink:
        """Create a link between a parent user and a student."""
        # Verify student exists
        await self.get_student(student_id)

        # Check for existing link
        result = await self.db.execute(
            select(ParentStudentLink).where(
                ParentStudentLink.user_id == user_id,
                ParentStudentLink.student_id == student_id,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError("Parent-student link already exists")

        link = ParentStudentLink(
            user_id=user_id,
            student_id=student_id,
            relationship_type=relationship_type,
        )
        self.db.add(link)
        await self.db.flush()

        logger.info(
            "parent_student.linked",
            user_id=str(user_id),
            student_id=str(student_id),
        )
        return link

    async def unlink_parent(
        self, user_id: uuid.UUID, student_id: uuid.UUID
    ) -> None:
        """Remove the link between a parent user and a student."""
        result = await self.db.execute(
            select(ParentStudentLink).where(
                ParentStudentLink.user_id == user_id,
                ParentStudentLink.student_id == student_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            raise NotFoundError("ParentStudentLink")

        await self.db.delete(link)
        await self.db.flush()

        logger.info(
            "parent_student.unlinked",
            user_id=str(user_id),
            student_id=str(student_id),
        )

    # --- Teacher-Student Assignment operations ---

    async def get_assigned_student_ids(self, teacher_user_id: uuid.UUID) -> list[uuid.UUID]:
        """Get all student IDs assigned to a teacher user."""
        result = await self.db.execute(
            select(TeacherStudentAssignment.student_id).where(
                TeacherStudentAssignment.user_id == teacher_user_id
            )
        )
        return list(result.scalars().all())

    async def get_student_teachers(self, student_id: uuid.UUID) -> list[TeacherStudentAssignment]:
        """Get all teacher assignments for a student."""
        result = await self.db.execute(
            select(TeacherStudentAssignment).where(
                TeacherStudentAssignment.student_id == student_id
            )
        )
        return list(result.scalars().all())

    async def assign_teacher(
        self,
        teacher_user_id: uuid.UUID,
        student_id: uuid.UUID,
        assigned_by_user_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> TeacherStudentAssignment:
        """Assign a teacher to a student."""
        await self.get_student(student_id)

        result = await self.db.execute(
            select(TeacherStudentAssignment).where(
                TeacherStudentAssignment.user_id == teacher_user_id,
                TeacherStudentAssignment.student_id == student_id,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError("Teacher-student assignment already exists")

        assignment = TeacherStudentAssignment(
            user_id=teacher_user_id,
            student_id=student_id,
            assigned_by_user_id=assigned_by_user_id,
            notes=notes,
        )
        self.db.add(assignment)
        await self.db.flush()

        logger.info(
            "teacher_student.assigned",
            teacher_user_id=str(teacher_user_id),
            student_id=str(student_id),
            assigned_by=str(assigned_by_user_id),
        )
        await event_bus.emit(
            "teacher_student.assigned",
            teacher_user_id=teacher_user_id,
            student_id=student_id,
        )
        return assignment

    async def unassign_teacher(
        self, teacher_user_id: uuid.UUID, student_id: uuid.UUID
    ) -> None:
        """Remove a teacher-student assignment."""
        result = await self.db.execute(
            select(TeacherStudentAssignment).where(
                TeacherStudentAssignment.user_id == teacher_user_id,
                TeacherStudentAssignment.student_id == student_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise NotFoundError("TeacherStudentAssignment")

        await self.db.delete(assignment)
        await self.db.flush()

        logger.info(
            "teacher_student.unassigned",
            teacher_user_id=str(teacher_user_id),
            student_id=str(student_id),
        )
        await event_bus.emit(
            "teacher_student.unassigned",
            teacher_user_id=teacher_user_id,
            student_id=student_id,
        )

    async def transfer_student(
        self,
        student_id: uuid.UUID,
        from_teacher_user_id: uuid.UUID,
        to_teacher_user_id: uuid.UUID,
        transferred_by_user_id: uuid.UUID | None = None,
    ) -> TeacherStudentAssignment:
        """Transfer a student from one teacher to another."""
        await self.unassign_teacher(from_teacher_user_id, student_id)
        new_assignment = await self.assign_teacher(
            teacher_user_id=to_teacher_user_id,
            student_id=student_id,
            assigned_by_user_id=transferred_by_user_id,
            notes=f"Overgenomen van docent {from_teacher_user_id}",
        )

        logger.info(
            "teacher_student.transferred",
            student_id=str(student_id),
            from_teacher=str(from_teacher_user_id),
            to_teacher=str(to_teacher_user_id),
        )
        await event_bus.emit(
            "teacher_student.transferred",
            student_id=student_id,
            from_teacher_user_id=from_teacher_user_id,
            to_teacher_user_id=to_teacher_user_id,
        )
        return new_assignment

    async def get_unassigned_students(
        self, page: int = 1, per_page: int = 25
    ) -> tuple[list[Student], int]:
        """Get active students not assigned to any teacher."""
        assigned_subq = select(TeacherStudentAssignment.student_id)
        query = select(Student).where(
            Student.is_active,
            ~Student.id.in_(assigned_subq),
        )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Student.first_name, Student.last_name)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        students = list(result.scalars().all())
        return students, total
