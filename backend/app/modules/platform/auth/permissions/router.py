import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import permission_registry
from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import (
    get_current_user,
    require_permission,
)
from app.modules.platform.auth.models import User
from app.modules.platform.auth.permissions.schemas import (
    EffectivePermissionsResponse,
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    GroupUserResponse,
    ModulePermissionsResponse,
    PermissionDefResponse,
    PermissionRegistryResponse,
    UserAssignment,
)
from app.modules.platform.auth.permissions.service import PermissionService

# Platform-scoped router: no tenant context needed
platform_router = APIRouter(prefix="/permissions", tags=["permissions"])

# Tenant-scoped router: requires tenant context (mounted under /schools/{slug})
tenant_router = APIRouter(prefix="/permissions", tags=["permissions"])


@platform_router.get("/registry", response_model=PermissionRegistryResponse)
async def get_registry(
    current_user: User = Depends(get_current_user),
):
    """List all registered modules and their permissions (from code)."""
    modules = permission_registry.get_all_modules()
    return PermissionRegistryResponse(
        modules=[
            ModulePermissionsResponse(
                module_name=m.module_name,
                label=m.label,
                permissions=[
                    PermissionDefResponse(
                        codename=p.codename,
                        label=p.label,
                        description=p.description,
                    )
                    for p in m.permissions
                ],
            )
            for m in modules
        ]
    )


@tenant_router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    request: Request,
    current_user: User = Depends(require_permission("school_settings.view", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """List all permission groups for the current tenant."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    return await service.list_groups(tenant_id)


@tenant_router.post("/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.edit", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Create a new permission group."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    result = await service.create_group(
        tenant_id=tenant_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@tenant_router.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.view", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Get a permission group detail."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    return await service.get_group(group_id, tenant_id)


@tenant_router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    data: GroupUpdate,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.edit", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Update a permission group."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    result = await service.update_group(
        group_id=group_id,
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@tenant_router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.edit", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Delete a permission group. Default groups cannot be deleted."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    await service.delete_group(group_id, tenant_id)
    await db.commit()


@tenant_router.get("/groups/{group_id}/users", response_model=list[GroupUserResponse])
async def list_group_users(
    group_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.view", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """List users assigned to a group."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    return await service.list_group_users(group_id, tenant_id)


@tenant_router.post("/groups/{group_id}/users", status_code=201)
async def assign_user_to_group(
    group_id: uuid.UUID,
    data: UserAssignment,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.edit", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Assign a user to a group."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    await service.assign_user(group_id, data.user_id, tenant_id)
    await db.commit()
    return {"message": "User assigned to group"}


@tenant_router.delete("/groups/{group_id}/users/{user_id}", status_code=204)
async def remove_user_from_group(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("school_settings.edit", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    """Remove a user from a group."""
    tenant_id = request.state.tenant_id
    service = PermissionService(db)
    await service.remove_user(group_id, user_id, tenant_id)
    await db.commit()


@tenant_router.get("/my-permissions", response_model=EffectivePermissionsResponse)
async def get_my_permissions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_central_db),
):
    """Get current user's effective permissions for the current tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    service = PermissionService(db)
    return await service.get_my_permissions(current_user, tenant_id)
