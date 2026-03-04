import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.core.security import verify_password
from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import (
    get_current_user,
    get_effective_permissions,
    require_permission,
)
from app.modules.platform.auth.models import TenantMembership, User
from app.modules.platform.tenant_mgmt.schemas import (
    TenantCreate,
    TenantDeleteConfirm,
    TenantResponse,
    TenantSettingsResponse,
    TenantSettingsUpdate,
)
from app.modules.platform.tenant_mgmt.service import TenantService

router = APIRouter(prefix="/orgs", tags=["orgs"])


async def get_tenant_service(
    db: AsyncSession = Depends(get_central_db),
) -> TenantService:
    return TenantService(db)


@router.post("/", response_model=TenantResponse, status_code=201)
async def create_tenant(
    data: TenantCreate,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
):
    return await service.create_tenant(data, owner_id=current_user.id)


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    perms = get_effective_permissions(current_user, tenant_id)
    if "platform.view_orgs" in perms:
        return await service.list_tenants()
    return await service.list_tenants(user_id=current_user.id)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    ctx_tenant_id = getattr(request.state, "tenant_id", None)
    perms = get_effective_permissions(current_user, ctx_tenant_id)
    if "platform.view_orgs" not in perms:
        is_member = any(
            a.group.tenant_id == tenant_id
            for a in current_user.group_assignments
        )
        if not is_member:
            # Fallback: check legacy memberships
            is_member = any(
                m.tenant_id == tenant_id and m.is_active
                for m in current_user.memberships
            )
        if not is_member:
            raise ForbiddenError()
    return await service.get_tenant(tenant_id)


@router.post("/{tenant_id}/provision", response_model=TenantResponse)
async def provision_tenant(
    tenant_id: uuid.UUID,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
):
    return await service.provision_tenant(tenant_id)


@router.delete("/{tenant_id}", response_model=TenantResponse)
async def delete_tenant(
    tenant_id: uuid.UUID,
    body: TenantDeleteConfirm,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
):
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return await service.delete_tenant(tenant_id)


@router.get("/{tenant_id}/settings", response_model=TenantSettingsResponse)
async def get_settings(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    # Verify user has access to this tenant
    if not current_user.is_superadmin:
        result = await db.execute(
            select(TenantMembership.id).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Not found")
    return await service.get_settings(tenant_id)


@router.put("/{tenant_id}/settings", response_model=TenantSettingsResponse)
async def update_settings(
    tenant_id: uuid.UUID,
    data: TenantSettingsUpdate,
    current_user: User = Depends(require_permission("org_settings.edit", hidden=True)),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    # Verify user has access to this tenant
    if not current_user.is_superadmin:
        result = await db.execute(
            select(TenantMembership.id).where(
                TenantMembership.user_id == current_user.id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Not found")
    return await service.update_settings(tenant_id, data)
