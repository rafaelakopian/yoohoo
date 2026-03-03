import uuid

import structlog
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_dependency import TenantAuditHelper, get_tenant_audit
from app.dependencies import get_tenant_db

from app.modules.platform.auth.dependencies import (
    DataScope,
    get_data_scope,
    require_any_permission,
    require_permission,
)
from app.modules.platform.auth.models import User
from app.modules.tenant.student.excel_import import parse_excel
from app.modules.tenant.student.schemas import (
    ParentStudentLinkCreate,
    ParentStudentLinkList,
    ParentStudentLinkResponse,
    StudentCreate,
    StudentImportResponse,
    StudentListResponse,
    StudentResponse,
    StudentUpdate,
    TeacherStudentAssignmentCreate,
    TeacherStudentAssignmentList,
    TeacherStudentAssignmentResponse,
    TeacherStudentTransfer,
)
from app.modules.tenant.student.service import StudentService

logger = structlog.get_logger()

# XLSX magic bytes (ZIP/OOXML: PK\x03\x04)
_XLSX_MAGIC = b"\x50\x4b\x03\x04"

router = APIRouter(prefix="/students", tags=["students"])


async def get_student_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> StudentService:
    return StudentService(db)


@router.get("/", response_model=StudentListResponse)
async def list_students(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    active: bool = Query(True),
    current_user: User = Depends(require_any_permission(
        "students.view", "students.view_assigned", "students.view_own", hidden=True
    )),
    service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "students")

    parent_user_id = None
    teacher_user_id = None

    if scope == DataScope.own:
        parent_user_id = current_user.id
    elif scope == DataScope.assigned:
        teacher_user_id = current_user.id

    students, total = await service.list_students(
        page=page,
        per_page=per_page,
        search=search,
        active_only=active,
        parent_user_id=parent_user_id,
        teacher_user_id=teacher_user_id,
    )
    return StudentListResponse(
        items=students, total=total, page=page, per_page=per_page
    )


@router.get("/my-children", response_model=StudentListResponse)
async def list_my_children(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_any_permission(
        "students.view", "students.view_own", hidden=True
    )),
    service: StudentService = Depends(get_student_service),
):
    """List students linked to the current parent user."""
    students, total = await service.list_students(
        page=page,
        per_page=per_page,
        parent_user_id=current_user.id,
    )
    return StudentListResponse(
        items=students, total=total, page=page, per_page=per_page
    )


@router.get("/my-students", response_model=StudentListResponse)
async def list_my_students(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    current_user: User = Depends(require_any_permission(
        "students.view", "students.view_assigned", hidden=True
    )),
    service: StudentService = Depends(get_student_service),
):
    """List students assigned to the current teacher."""
    students, total = await service.list_students(
        page=page,
        per_page=per_page,
        search=search,
        teacher_user_id=current_user.id,
    )
    return StudentListResponse(
        items=students, total=total, page=page, per_page=per_page
    )


@router.get("/unassigned", response_model=StudentListResponse)
async def list_unassigned_students(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_permission("students.assign", hidden=True)),
    service: StudentService = Depends(get_student_service),
):
    """List students not assigned to any teacher."""
    students, total = await service.get_unassigned_students(page=page, per_page=per_page)
    return StudentListResponse(
        items=students, total=total, page=page, per_page=per_page
    )


@router.post("/self-assign/{student_id}", response_model=TeacherStudentAssignmentResponse, status_code=201)
async def self_assign_student(
    student_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "students.assign", "students.view_assigned", hidden=True
    )),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Self-assign an unassigned student to the current teacher."""
    teachers = await service.get_student_teachers(student_id)
    if teachers:
        from app.core.exceptions import ConflictError
        raise ConflictError("Leerling is al toegewezen aan een docent. Gebruik transfer.")

    result = await service.assign_teacher(
        teacher_user_id=current_user.id,
        student_id=student_id,
        assigned_by_user_id=current_user.id,
        notes="Zelf toegewezen",
    )
    await audit.log("teacher.self_assigned", entity_type="student", entity_id=student_id)
    return result


@router.post("/", response_model=StudentResponse, status_code=201)
async def create_student(
    data: StudentCreate,
    current_user: User = Depends(require_permission("students.create", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    student = await service.create_student(data)
    await audit.log("student.created", entity_type="student", entity_id=student.id)
    return student


@router.post("/import", response_model=StudentImportResponse)
async def import_students(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("students.import", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    # Validate file type (MIME)
    allowed_types = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
    if file.content_type and file.content_type not in allowed_types:
        return StudentImportResponse(
            imported=0, skipped=0, errors=["Alleen Excel-bestanden (.xlsx, .xls) zijn toegestaan"]
        )

    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        return StudentImportResponse(
            imported=0, skipped=0, errors=["Bestand is te groot (max 5MB)"]
        )

    # Validate file signature (magic bytes) — XLSX is a ZIP archive (PK\x03\x04)
    if len(contents) < 4 or contents[:4] != _XLSX_MAGIC:
        return StudentImportResponse(
            imported=0, skipped=0, errors=["Ongeldig bestandsformaat — alleen .xlsx bestanden zijn toegestaan"]
        )

    logger.info(
        "student.import_started",
        user_id=str(current_user.id),
        file_name=file.filename,
        file_size=len(contents),
    )

    students, parse_errors = parse_excel(contents)

    if not students:
        return StudentImportResponse(imported=0, skipped=0, errors=parse_errors)

    result = await service.bulk_import(students)
    result.errors.extend(parse_errors)

    logger.info(
        "student.import_completed",
        user_id=str(current_user.id),
        imported=result.imported,
        skipped=result.skipped,
        errors=len(result.errors),
    )

    await audit.log(
        "student.imported", entity_type="student",
        imported=result.imported, skipped=result.skipped, errors=len(result.errors),
    )

    return result


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    request: Request,
    student_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "students.view", "students.view_assigned", "students.view_own", hidden=True
    )),
    service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "students")

    if scope == DataScope.own:
        return await service.get_student(student_id, parent_user_id=current_user.id)
    elif scope == DataScope.assigned:
        return await service.get_student(student_id, teacher_user_id=current_user.id)
    return await service.get_student(student_id)


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    data: StudentUpdate,
    current_user: User = Depends(require_permission("students.edit", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    student = await service.update_student(student_id, data)
    await audit.log("student.updated", entity_type="student", entity_id=student_id)
    return student


@router.delete("/{student_id}", response_model=StudentResponse)
async def delete_student(
    student_id: uuid.UUID,
    current_user: User = Depends(require_permission("students.delete", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    student = await service.delete_student(student_id)
    await audit.log("student.deleted", entity_type="student", entity_id=student_id)
    return student


# --- Parent-Student link management (admin only) ---


@router.get("/{student_id}/parents", response_model=ParentStudentLinkList)
async def list_student_parents(
    student_id: uuid.UUID,
    current_user: User = Depends(require_permission("students.manage_parents", hidden=True)),
    service: StudentService = Depends(get_student_service),
):
    """List all parent links for a student."""
    links = await service.get_linked_parents(student_id)
    return ParentStudentLinkList(items=links)


@router.post("/{student_id}/parents", response_model=ParentStudentLinkResponse, status_code=201)
async def link_parent_to_student(
    student_id: uuid.UUID,
    data: ParentStudentLinkCreate,
    current_user: User = Depends(require_permission("students.manage_parents", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Link a parent user to a student."""
    result = await service.link_parent(
        user_id=data.user_id,
        student_id=student_id,
        relationship_type=data.relationship_type,
    )
    await audit.log("parent.linked", entity_type="student", entity_id=student_id, parent_user_id=str(data.user_id))
    return result


@router.delete("/{student_id}/parents/{user_id}", status_code=204)
async def unlink_parent_from_student(
    student_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("students.manage_parents", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Remove a parent-student link."""
    await service.unlink_parent(user_id=user_id, student_id=student_id)
    await audit.log("parent.unlinked", entity_type="student", entity_id=student_id, parent_user_id=str(user_id))


# --- Teacher-Student assignment management ---


@router.get("/{student_id}/teachers", response_model=TeacherStudentAssignmentList)
async def list_student_teachers(
    student_id: uuid.UUID,
    current_user: User = Depends(require_permission("students.assign", hidden=True)),
    service: StudentService = Depends(get_student_service),
):
    """List all teacher assignments for a student."""
    assignments = await service.get_student_teachers(student_id)
    return TeacherStudentAssignmentList(items=assignments)


@router.post("/{student_id}/teachers", response_model=TeacherStudentAssignmentResponse, status_code=201)
async def assign_teacher_to_student(
    student_id: uuid.UUID,
    data: TeacherStudentAssignmentCreate,
    current_user: User = Depends(require_permission("students.assign", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Assign a teacher to a student."""
    result = await service.assign_teacher(
        teacher_user_id=data.user_id,
        student_id=student_id,
        assigned_by_user_id=current_user.id,
        notes=data.notes,
    )
    await audit.log("teacher.assigned", entity_type="student", entity_id=student_id, teacher_user_id=str(data.user_id))
    return result


@router.delete("/{student_id}/teachers/{teacher_user_id}", status_code=204)
async def unassign_teacher_from_student(
    student_id: uuid.UUID,
    teacher_user_id: uuid.UUID,
    current_user: User = Depends(require_permission("students.assign", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Remove a teacher-student assignment."""
    await service.unassign_teacher(teacher_user_id=teacher_user_id, student_id=student_id)
    await audit.log("teacher.unassigned", entity_type="student", entity_id=student_id, teacher_user_id=str(teacher_user_id))


@router.post("/{student_id}/transfer", response_model=TeacherStudentAssignmentResponse)
async def transfer_student_between_teachers(
    student_id: uuid.UUID,
    data: TeacherStudentTransfer,
    current_user: User = Depends(require_permission("students.assign", hidden=True)),
    service: StudentService = Depends(get_student_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    """Transfer a student from one teacher to another."""
    result = await service.transfer_student(
        student_id=student_id,
        from_teacher_user_id=data.from_teacher_user_id,
        to_teacher_user_id=data.to_teacher_user_id,
        transferred_by_user_id=current_user.id,
    )
    await audit.log(
        "student.transferred", entity_type="student", entity_id=student_id,
        from_teacher=str(data.from_teacher_user_id), to_teacher=str(data.to_teacher_user_id),
    )
    return result
