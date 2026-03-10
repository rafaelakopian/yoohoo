import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.core.middleware import get_client_ip
from app.core.security import verify_password
from app.db.central import get_central_db
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.dependencies import (
    get_current_user,
    get_effective_permissions,
    require_permission,
)
from app.modules.platform.auth.models import TenantMembership, User
from app.modules.platform.tenant_mgmt.schemas import (
    SelfServiceOrgCreate,
    SlugCheckResponse,
    TenantCreate,
    TenantDeleteConfirm,
    TenantResponse,
    TenantSettingsResponse,
    TenantSettingsUpdate,
)
from app.modules.platform.tenant_mgmt.service import TenantService

router = APIRouter(prefix="/platform/orgs", tags=["orgs"])


async def get_tenant_service(
    db: AsyncSession = Depends(get_central_db),
) -> TenantService:
    return TenantService(db)


@router.post("/", response_model=TenantResponse, status_code=201)
async def create_tenant(
    data: TenantCreate,
    request: Request,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    tenant = await service.create_tenant(data, owner_id=current_user.id)
    audit = AuditService(db)
    await audit.log(
        action="tenant.created",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        entity_type="tenant",
        entity_id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
    )
    return tenant


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    perms = get_effective_permissions(current_user, tenant_id)
    if "platform.view_orgs" in perms:
        return await service.list_tenants_enriched()
    return await service.list_tenants(user_id=current_user.id)


@router.get("/check-slug", response_model=SlugCheckResponse)
async def check_slug(
    slug: str = Query(..., min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"),
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    available = await service.check_slug_available(slug)
    return {"slug": slug, "available": available}


@router.post("/self-service", response_model=TenantResponse, status_code=201)
async def self_service_create(
    data: SelfServiceOrgCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    tenant = await service.self_service_create(data, user_id=current_user.id)
    audit = AuditService(db)
    await audit.log(
        action="tenant.self_service_created",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        entity_type="tenant",
        entity_id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        plan_id=str(data.plan_id),
    )
    await db.commit()
    return tenant


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
    request: Request,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    tenant = await service.provision_tenant(tenant_id)
    audit = AuditService(db)
    await audit.log(
        action="tenant.provisioned",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        entity_type="tenant",
        entity_id=tenant.id,
        slug=tenant.slug,
    )
    return tenant


@router.delete("/{tenant_id}", response_model=TenantResponse)
async def delete_tenant(
    tenant_id: uuid.UUID,
    body: TenantDeleteConfirm,
    request: Request,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: TenantService = Depends(get_tenant_service),
    db: AsyncSession = Depends(get_central_db),
):
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    # Capture details before delete removes the tenant
    tenant = await service.get_tenant(tenant_id)
    tenant_slug = tenant.slug
    tenant_name = tenant.name
    await service.delete_tenant(tenant_id)
    audit = AuditService(db)
    await audit.log(
        action="tenant.deleted",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        entity_type="tenant",
        entity_id=tenant_id,
        slug=tenant_slug,
        name=tenant_name,
    )
    return tenant


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
    request: Request,
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
    settings = await service.update_settings(tenant_id, data)
    audit = AuditService(db)
    await audit.log(
        action="tenant.settings_updated",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        entity_type="tenant",
        entity_id=tenant_id,
        fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    return settings
