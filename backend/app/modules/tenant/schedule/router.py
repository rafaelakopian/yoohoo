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
from app.modules.tenant.schedule.models import LessonStatus
from app.modules.tenant.schedule.schemas import (
    CalendarWeekResponse,
    GenerateLessonsRequest,
    GenerateLessonsResponse,
    HolidayCreate,
    HolidayListResponse,
    HolidayResponse,
    HolidayUpdate,
    LessonInstanceCreate,
    LessonInstanceListResponse,
    LessonInstanceReschedule,
    LessonInstanceResponse,
    LessonInstanceUpdate,
    LessonSlotCreate,
    LessonSlotListResponse,
    LessonSlotResponse,
    LessonSlotUpdate,
    SubstitutionCreate,
)
from app.modules.tenant.schedule.service import ScheduleService
from app.modules.tenant.student.service import StudentService

router = APIRouter(prefix="/schedule", tags=["schedule"])


async def get_schedule_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> ScheduleService:
    return ScheduleService(db)


async def get_student_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> StudentService:
    return StudentService(db)


# ─── Slots ───


@router.get("/slots/", response_model=LessonSlotListResponse)
async def list_slots(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    student_id: uuid.UUID | None = Query(None),
    day_of_week: int | None = Query(None, ge=1, le=7),
    active_only: bool = Query(True),
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
    student_service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "schedule")

    student_ids = None

    if scope == DataScope.assigned:
        student_ids = await student_service.get_assigned_student_ids(current_user.id)
        if not student_ids:
            return LessonSlotListResponse(items=[], total=0, page=page, per_page=per_page)

    slots, total = await service.list_slots(
        page=page,
        per_page=per_page,
        student_id=student_id,
        day_of_week=day_of_week,
        active_only=active_only,
        student_ids=student_ids,
    )
    return LessonSlotListResponse(
        items=slots, total=total, page=page, per_page=per_page
    )


@router.post("/slots/", response_model=LessonSlotResponse, status_code=201)
async def create_slot(
    data: LessonSlotCreate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    slot = await service.create_slot(data)
    await audit.log("schedule_slot.created", entity_type="schedule_slot", entity_id=slot.id)
    return slot


@router.get("/slots/{slot_id}", response_model=LessonSlotResponse)
async def get_slot(
    slot_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
):
    return await service.get_slot(slot_id)


@router.put("/slots/{slot_id}", response_model=LessonSlotResponse)
async def update_slot(
    slot_id: uuid.UUID,
    data: LessonSlotUpdate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    slot = await service.update_slot(slot_id, data)
    await audit.log("schedule_slot.updated", entity_type="schedule_slot", entity_id=slot_id)
    return slot


@router.delete("/slots/{slot_id}", response_model=LessonSlotResponse)
async def delete_slot(
    slot_id: uuid.UUID,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    slot = await service.delete_slot(slot_id)
    await audit.log("schedule_slot.deleted", entity_type="schedule_slot", entity_id=slot_id)
    return slot


# ─── Lessons (Instances) ───


@router.get("/lessons/", response_model=LessonInstanceListResponse)
async def list_lessons(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    student_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status: LessonStatus | None = Query(None),
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
    student_service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "schedule")

    student_ids = None

    if scope == DataScope.assigned:
        student_ids = await student_service.get_assigned_student_ids(current_user.id)
        if not student_ids:
            return LessonInstanceListResponse(items=[], total=0, page=page, per_page=per_page)

    instances, total = await service.list_instances(
        page=page,
        per_page=per_page,
        student_id=student_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        student_ids=student_ids,
    )
    return LessonInstanceListResponse(
        items=instances, total=total, page=page, per_page=per_page
    )


@router.post("/lessons/", response_model=LessonInstanceResponse, status_code=201)
async def create_lesson(
    data: LessonInstanceCreate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    instance = await service.create_instance(data)
    await audit.log("schedule_instance.created", entity_type="schedule_instance", entity_id=instance.id)
    return instance


@router.post("/lessons/generate", response_model=GenerateLessonsResponse)
async def generate_lessons(
    data: GenerateLessonsRequest,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    result = await service.generate_instances(data)
    await audit.log("schedule_instance.generated", entity_type="schedule_instance", count=result.generated)
    return result


@router.get("/lessons/{instance_id}", response_model=LessonInstanceResponse)
async def get_lesson(
    instance_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
):
    return await service.get_instance(instance_id)


@router.put("/lessons/{instance_id}", response_model=LessonInstanceResponse)
async def update_lesson(
    instance_id: uuid.UUID,
    data: LessonInstanceUpdate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    instance = await service.update_instance(instance_id, data)
    await audit.log("schedule_instance.updated", entity_type="schedule_instance", entity_id=instance_id)
    return instance


@router.post("/lessons/{instance_id}/cancel", response_model=LessonInstanceResponse)
async def cancel_lesson(
    instance_id: uuid.UUID,
    reason: str | None = None,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    instance = await service.cancel_instance(instance_id, reason)
    await audit.log("schedule_instance.cancelled", entity_type="schedule_instance", entity_id=instance_id)
    return instance


@router.post("/lessons/{instance_id}/reschedule", response_model=LessonInstanceResponse)
async def reschedule_lesson(
    instance_id: uuid.UUID,
    data: LessonInstanceReschedule,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    instance = await service.reschedule_instance(instance_id, data)
    await audit.log("schedule_instance.rescheduled", entity_type="schedule_instance", entity_id=instance_id)
    return instance


# ─── Substitution ───


@router.post("/lessons/{instance_id}/substitute", response_model=LessonInstanceResponse)
async def assign_substitute(
    instance_id: uuid.UUID,
    data: SubstitutionCreate,
    current_user: User = Depends(require_any_permission(
        "schedule.substitute", "schedule.manage", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    instance = await service.assign_substitute(
        instance_id=instance_id,
        substitute_teacher_user_id=data.substitute_teacher_user_id,
        reason=data.reason,
    )
    await audit.log(
        "schedule_instance.substituted", entity_type="schedule_instance", entity_id=instance_id,
        substitute_teacher=str(data.substitute_teacher_user_id),
    )
    return instance


# ─── Holidays ───


@router.get("/holidays/", response_model=HolidayListResponse)
async def list_holidays(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
):
    holidays, total = await service.list_holidays(page=page, per_page=per_page)
    return HolidayListResponse(
        items=holidays, total=total, page=page, per_page=per_page
    )


@router.post("/holidays/", response_model=HolidayResponse, status_code=201)
async def create_holiday(
    data: HolidayCreate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    holiday = await service.create_holiday(data)
    await audit.log("holiday.created", entity_type="holiday", entity_id=holiday.id)
    return holiday


@router.get("/holidays/{holiday_id}", response_model=HolidayResponse)
async def get_holiday(
    holiday_id: uuid.UUID,
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
):
    return await service.get_holiday(holiday_id)


@router.put("/holidays/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: uuid.UUID,
    data: HolidayUpdate,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    holiday = await service.update_holiday(holiday_id, data)
    await audit.log("holiday.updated", entity_type="holiday", entity_id=holiday_id)
    return holiday


@router.delete("/holidays/{holiday_id}", response_model=HolidayResponse)
async def delete_holiday(
    holiday_id: uuid.UUID,
    current_user: User = Depends(require_permission("schedule.manage", hidden=True)),
    service: ScheduleService = Depends(get_schedule_service),
    audit: TenantAuditHelper = Depends(get_tenant_audit),
):
    holiday = await service.delete_holiday(holiday_id)
    await audit.log("holiday.deleted", entity_type="holiday", entity_id=holiday_id)
    return holiday


# ─── Calendar ───


@router.get("/calendar/week", response_model=CalendarWeekResponse)
async def get_calendar_week(
    request: Request,
    start: date = Query(..., description="Week start date (Monday)"),
    current_user: User = Depends(require_any_permission(
        "schedule.view", "schedule.view_assigned", hidden=True
    )),
    service: ScheduleService = Depends(get_schedule_service),
    student_service: StudentService = Depends(get_student_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    scope = get_data_scope(current_user, tenant_id, "schedule")

    student_ids = None

    if scope == DataScope.assigned:
        student_ids = await student_service.get_assigned_student_ids(current_user.id)

    return await service.get_calendar_week(
        week_start=start,
        student_ids=student_ids,
    )
