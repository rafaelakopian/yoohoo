"""Operations API — platform monitoring, insights & support tooling."""

import uuid
from datetime import datetime

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.dependencies import get_arq
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.operations.job_monitor import JobQueueSummary, get_job_summary
from app.modules.platform.operations.schemas import (
    AuditEvent,
    Disable2FARequest,
    ImpersonateRequest,
    ImpersonateResponse,
    OnboardingItem,
    RevokeSessionsResponse,
    SupportNoteCreate,
    SupportNoteResponse,
    SupportNoteUpdate,
    Tenant360Detail,
    TenantHealthDashboard,
    TimelineResponse,
    ToggleActiveRequest,
    ToggleActiveResponse,
)
from app.modules.platform.operations.service import OperationsService

router = APIRouter(prefix="/platform/operations", tags=["operations"])


def get_operations_service(db: AsyncSession = Depends(get_central_db)) -> OperationsService:
    return OperationsService(db)


# --- A1: Tenant Health Dashboard ---

@router.get(
    "/dashboard",
    response_model=TenantHealthDashboard,
)
async def get_operations_dashboard(
    _: User = Depends(require_permission("operations.view_dashboard")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.get_tenant_health_dashboard()


# --- A2: Tenant 360° Detail ---

@router.get(
    "/tenants/{tenant_id}",
    response_model=Tenant360Detail,
)
async def get_tenant_360(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("operations.view_tenant_detail")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.get_tenant_360(tenant_id)


@router.get(
    "/tenants/{tenant_id}/events",
    response_model=list[AuditEvent],
)
async def get_tenant_events(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("operations.view_tenant_detail")),
    service: OperationsService = Depends(get_operations_service),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await service.get_tenant_events(tenant_id, limit=limit, offset=offset)


# --- B3: Customer Timeline ---

@router.get(
    "/tenants/{tenant_id}/timeline",
    response_model=TimelineResponse,
)
async def get_tenant_timeline(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("operations.view_tenant_detail")),
    service: OperationsService = Depends(get_operations_service),
    category: str | None = Query(default=None, pattern="^(login|security|data|billing|system)$"),
    user_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, min_length=2, max_length=100),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await service.get_tenant_timeline(
        tenant_id,
        category=category,
        user_id=user_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


# --- A4: Onboarding Overview ---

@router.get(
    "/onboarding",
    response_model=list[OnboardingItem],
)
async def get_onboarding_overview(
    _: User = Depends(require_permission("operations.view_onboarding")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.get_onboarding_overview()


# --- B4: Support Notes ---

@router.get(
    "/tenants/{tenant_id}/notes",
    response_model=list[SupportNoteResponse],
)
async def get_tenant_notes(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.list_tenant_notes(tenant_id)


@router.post(
    "/tenants/{tenant_id}/notes",
    response_model=SupportNoteResponse,
    status_code=201,
)
async def create_tenant_note(
    tenant_id: uuid.UUID,
    data: SupportNoteCreate,
    user: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.create_tenant_note(tenant_id, user, data)


@router.get(
    "/users/{user_id}/notes",
    response_model=list[SupportNoteResponse],
)
async def get_user_notes(
    user_id: uuid.UUID,
    _: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.list_user_notes(user_id)


@router.post(
    "/users/{user_id}/notes",
    response_model=SupportNoteResponse,
    status_code=201,
)
async def create_user_note(
    user_id: uuid.UUID,
    data: SupportNoteCreate,
    user: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.create_user_note(user_id, user, data)


@router.put(
    "/notes/{note_id}",
    response_model=SupportNoteResponse,
)
async def update_note(
    note_id: uuid.UUID,
    data: SupportNoteUpdate,
    user: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.update_note(note_id, user, data)


@router.delete(
    "/notes/{note_id}",
    status_code=204,
)
async def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    await service.delete_note(note_id, user)


@router.patch(
    "/notes/{note_id}/pin",
    response_model=SupportNoteResponse,
)
async def toggle_pin_note(
    note_id: uuid.UUID,
    user: User = Depends(require_permission("operations.manage_notes")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.toggle_pin_note(note_id, user)


# --- B2: Quick Actions ---

@router.post("/users/{user_id}/force-password-reset", status_code=204)
async def force_password_reset(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("operations.manage_users")),
    service: OperationsService = Depends(get_operations_service),
):
    await service.force_password_reset(
        user, user_id,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


@router.post(
    "/users/{user_id}/toggle-active",
    response_model=ToggleActiveResponse,
)
async def toggle_user_active(
    user_id: uuid.UUID,
    data: ToggleActiveRequest,
    request: Request,
    user: User = Depends(require_permission("operations.manage_users")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.toggle_user_active(
        user, user_id, data.password,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


@router.post("/users/{user_id}/resend-verification", status_code=204)
async def resend_verification(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("operations.manage_users")),
    service: OperationsService = Depends(get_operations_service),
):
    await service.resend_verification_email(
        user, user_id,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


@router.post(
    "/users/{user_id}/revoke-sessions",
    response_model=RevokeSessionsResponse,
)
async def revoke_user_sessions(
    user_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("operations.manage_users")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.revoke_user_sessions(
        user, user_id,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


@router.post("/users/{user_id}/disable-2fa", status_code=204)
async def disable_user_2fa(
    user_id: uuid.UUID,
    data: Disable2FARequest,
    request: Request,
    user: User = Depends(require_permission("operations.manage_users")),
    service: OperationsService = Depends(get_operations_service),
):
    await service.disable_user_2fa(
        user, user_id, data.password,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


# --- B1: Impersonate ---

@router.post(
    "/impersonate",
    response_model=ImpersonateResponse,
)
async def impersonate_user(
    data: ImpersonateRequest,
    request: Request,
    user: User = Depends(require_permission("operations.impersonate")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.impersonate_user(
        user, data.user_id, data.reason,
        tenant_id=data.tenant_id,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )


# --- Job Monitoring ---


@router.get("/jobs", response_model=JobQueueSummary)
async def get_job_monitor(
    _: User = Depends(require_permission("operations.view_jobs")),
    arq_pool: ArqRedis | None = Depends(get_arq),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    """Actuele status van de arq job queue. Leest rechtstreeks uit Redis."""
    return await get_job_summary(arq_pool, date_from=date_from, date_to=date_to)
