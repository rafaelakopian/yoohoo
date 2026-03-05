"""Operations API — platform monitoring & insights (superadmin only)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.operations.schemas import (
    AuditEvent,
    OnboardingItem,
    Tenant360Detail,
    TenantHealthDashboard,
    UserLookupResult,
)
from app.modules.platform.operations.service import OperationsService

router = APIRouter(prefix="/admin/operations", tags=["operations"])


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


# --- A3: User Lookup ---

@router.get(
    "/users/lookup",
    response_model=list[UserLookupResult],
    dependencies=[Depends(rate_limit(30, 60, "rl:ops-user-lookup"))],
)
async def lookup_user(
    q: str = Query(min_length=3, max_length=100),
    _: User = Depends(require_permission("operations.view_users")),
    service: OperationsService = Depends(get_operations_service),
):
    return await service.lookup_user(q)


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
