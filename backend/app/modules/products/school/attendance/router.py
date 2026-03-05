import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
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
from app.modules.products.school.attendance.schemas import (
    AttendanceBulkCreate,
    AttendanceBulkResponse,
    AttendanceCreate,
    AttendanceListResponse,
    AttendanceResponse,
    AttendanceUpdate,
)
from app.modules.products.school.attendance.service import AttendanceService
from app.modules.products.school.student.service import StudentService

router = APIRouter(prefix="/attendance", tags=["attendance"])


async def get_attendance_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> AttendanceService:
    return AttendanceService(db)


async def get_student_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> StudentService:
    return StudentService(db)


@router.get("/", response_model=AttendanceListResponse)
async def list_attendance(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    student_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(require_any_permission(
        "attendance.view", "attendance.view_assigned", "attendance.view_own", hidden=True
    )),
    service: AttendanceService = Depends(get_attendance_service),
    student_service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "attendance")

    if scope == DataScope.assigned:
        # Teacher: only see attendance for assigned students
        assigned_ids = await student_service.get_assigned_student_ids(current_user.id)
        if not assigned_ids:
            return AttendanceListResponse(items=[], total=0, page=page, per_page=per_page)
        if student_id and student_id not in assigned_ids:
            return AttendanceListResponse(items=[], total=0, page=page, per_page=per_page)
        if not student_id:
            records, total = await service.list_for_students(
                student_ids=assigned_ids, page=page, per_page=per_page,
                date_from=date_from, date_to=date_to,
            )
            return AttendanceListResponse(items=records, total=total, page=page, per_page=per_page)

    elif scope == DataScope.own:
        # Parent: only see attendance for linked children
        linked_ids = await student_service.get_linked_student_ids(current_user.id)
        if not linked_ids:
            return AttendanceListResponse(items=[], total=0, page=page, per_page=per_page)
        if student_id and student_id not in linked_ids:
            return AttendanceListResponse(items=[], total=0, page=page, per_page=per_page)
        if not student_id:
            records, total = await service.list_for_students(
                student_ids=linked_ids, page=page, per_page=per_page,
                date_from=date_from, date_to=date_to,
            )
            return AttendanceListResponse(items=records, total=total, page=page, per_page=per_page)

    records, total = await service.list(
        page=page, per_page=per_page, student_id=student_id,
        date_from=date_from, date_to=date_to,
    )
    return AttendanceListResponse(items=records, total=total, page=page, per_page=per_page)


@router.post("/", response_model=AttendanceResponse, status_code=201)
async def create_attendance(
    data: AttendanceCreate,
    current_user: User = Depends(require_permission("attendance.create", hidden=True)),
    service: AttendanceService = Depends(get_attendance_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    data.recorded_by_user_id = current_user.id
    record = await service.create(data)
    await audit.log("attendance.created", entity_type="attendance", entity_id=record.id)
    return record


@router.post("/bulk", response_model=AttendanceBulkResponse)
async def bulk_create_attendance(
    data: AttendanceBulkCreate,
    current_user: User = Depends(require_permission("attendance.create", hidden=True)),
    service: AttendanceService = Depends(get_attendance_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    result = await service.bulk_create(data, recorded_by_user_id=current_user.id)
    await audit.log("attendance.bulk_created", entity_type="attendance", count=len(data.records))
    return result


@router.get("/{record_id}", response_model=AttendanceResponse)
async def get_attendance(
    request: Request,
    record_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "attendance.view", "attendance.view_assigned", "attendance.view_own", hidden=True
    )),
    service: AttendanceService = Depends(get_attendance_service),
    student_service: StudentService = Depends(get_student_service),
):
    record = await service.get(record_id)

    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "attendance")

    if scope == DataScope.assigned:
        assigned_ids = await student_service.get_assigned_student_ids(current_user.id)
        if record.student_id not in assigned_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError("You do not have access to this attendance record")
    elif scope == DataScope.own:
        linked_ids = await student_service.get_linked_student_ids(current_user.id)
        if record.student_id not in linked_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError("You do not have access to this attendance record")

    return record


@router.put("/{record_id}", response_model=AttendanceResponse)
async def update_attendance(
    record_id: uuid.UUID,
    data: AttendanceUpdate,
    current_user: User = Depends(require_permission("attendance.edit", hidden=True)),
    service: AttendanceService = Depends(get_attendance_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    record = await service.update(record_id, data)
    await audit.log("attendance.updated", entity_type="attendance", entity_id=record_id)
    return record


@router.delete("/{record_id}", response_model=AttendanceResponse)
async def delete_attendance(
    record_id: uuid.UUID,
    current_user: User = Depends(require_permission("attendance.delete", hidden=True)),
    service: AttendanceService = Depends(get_attendance_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    record = await service.delete(record_id)
    await audit.log("attendance.deleted", entity_type="attendance", entity_id=record_id)
    return record
