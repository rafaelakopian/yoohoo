import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.admin.schemas import (
    AddMembership,
    AdminTenantDetail,
    AdminTenantItem,
    AdminUserDetail,
    AdminUserUpdate,
    PaginatedAuditLogs,
    PaginatedUserList,
    PlatformStats,
    SuperAdminToggle,
    TransferOwnership,
)
from app.modules.platform.admin.service import AdminService
from app.modules.platform.auth.permissions.service import PermissionService
from app.modules.platform.auth.permissions.schemas import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    GroupUserResponse,
    UserAssignment,
)

router = APIRouter(prefix="/admin", tags=["platform-admin"])


async def get_admin_service(
    db: AsyncSession = Depends(get_central_db),
) -> AdminService:
    return AdminService(db)


async def get_permission_service(
    db: AsyncSession = Depends(get_central_db),
) -> PermissionService:
    return PermissionService(db)


@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats(
    _: User = Depends(require_permission("platform.view_stats")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_platform_stats()


@router.get("/schools", response_model=list[AdminTenantItem])
async def list_tenants(
    _: User = Depends(require_permission("platform.view_schools")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.list_tenants_admin()


@router.get("/schools/{tenant_id}/detail", response_model=AdminTenantDetail)
async def get_tenant_detail(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.view_schools")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_tenant_detail(tenant_id)


@router.get("/users", response_model=PaginatedUserList)
async def list_users(
    _: User = Depends(require_permission("platform.view_users")),
    service: AdminService = Depends(get_admin_service),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await service.list_users(search=search, is_active=is_active, skip=skip, limit=limit)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    _: User = Depends(require_permission("platform.view_users")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_user_detail(user_id)


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    _: User = Depends(require_permission("platform.edit_users")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.update_user(user_id, body.model_dump(exclude_unset=True))


@router.put("/users/{user_id}/superadmin")
async def toggle_superadmin(
    user_id: uuid.UUID,
    body: SuperAdminToggle,
    current_user: User = Depends(require_permission("platform.manage_superadmin")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.toggle_superadmin(user_id, body.is_superadmin, current_user_id=current_user.id)


@router.put("/schools/{tenant_id}/owner")
async def transfer_ownership(
    tenant_id: uuid.UUID,
    body: TransferOwnership,
    current_user: User = Depends(require_permission("platform.manage_schools")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.transfer_ownership(
        tenant_id, body.user_id, current_user_id=current_user.id,
    )


@router.post("/schools/{tenant_id}/memberships")
async def add_membership(
    tenant_id: uuid.UUID,
    body: AddMembership,
    _: User = Depends(require_permission("platform.manage_memberships")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.add_membership(tenant_id, body.user_id, body.role, group_id=body.group_id)


@router.delete("/schools/{tenant_id}/memberships/{user_id}", status_code=204)
async def remove_membership(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_memberships")),
    service: AdminService = Depends(get_admin_service),
):
    await service.remove_membership(tenant_id, user_id)


@router.get("/audit-logs", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    _: User = Depends(require_permission("platform.view_audit_logs")),
    service: AdminService = Depends(get_admin_service),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await service.list_audit_logs(
        user_id=user_id, action=action,
        date_from=date_from, date_to=date_to,
        skip=skip, limit=limit,
    )


# --- Permission Groups per Tenant ---


@router.get("/schools/{tenant_id}/groups", response_model=list[GroupResponse])
async def admin_list_groups(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_groups(tenant_id)


@router.post("/schools/{tenant_id}/groups", response_model=GroupResponse, status_code=201)
async def admin_create_group(
    tenant_id: uuid.UUID,
    data: GroupCreate,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    result = await service.create_group(
        tenant_id=tenant_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@router.get("/schools/{tenant_id}/groups/{group_id}", response_model=GroupResponse)
async def admin_get_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.get_group(group_id, tenant_id)


@router.put("/schools/{tenant_id}/groups/{group_id}", response_model=GroupResponse)
async def admin_update_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    data: GroupUpdate,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    result = await service.update_group(
        group_id=group_id,
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@router.delete("/schools/{tenant_id}/groups/{group_id}", status_code=204)
async def admin_delete_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.delete_group(group_id, tenant_id)
    await db.commit()


@router.get(
    "/schools/{tenant_id}/groups/{group_id}/users",
    response_model=list[GroupUserResponse],
)
async def admin_list_group_users(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_group_users(group_id, tenant_id)


@router.post("/schools/{tenant_id}/groups/{group_id}/users", status_code=201)
async def admin_assign_user_to_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    data: UserAssignment,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.assign_user(group_id, data.user_id, tenant_id)
    await db.commit()
    return {"message": "User assigned to group"}


@router.delete(
    "/schools/{tenant_id}/groups/{group_id}/users/{user_id}",
    status_code=204,
)
async def admin_remove_user_from_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.remove_user(group_id, user_id, tenant_id)
    await db.commit()


# --- Platform Groups (tenant_id IS NULL) ---


@router.get("/platform-groups", response_model=list[GroupResponse])
async def list_platform_groups(
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_platform_groups()


@router.post("/platform-groups", response_model=GroupResponse, status_code=201)
async def create_platform_group(
    data: GroupCreate,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    result = await service.create_platform_group(
        name=data.name,
        slug=data.slug,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@router.get("/platform-groups/{group_id}", response_model=GroupResponse)
async def get_platform_group(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.get_platform_group(group_id)


@router.put("/platform-groups/{group_id}", response_model=GroupResponse)
async def update_platform_group(
    group_id: uuid.UUID,
    data: GroupUpdate,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    result = await service.update_platform_group(
        group_id=group_id,
        name=data.name,
        description=data.description,
        permissions=data.permissions,
    )
    await db.commit()
    return result


@router.delete("/platform-groups/{group_id}", status_code=204)
async def delete_platform_group(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.delete_platform_group(group_id)
    await db.commit()


@router.get(
    "/platform-groups/{group_id}/users",
    response_model=list[GroupUserResponse],
)
async def list_platform_group_users(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_platform_group_users(group_id)


@router.post("/platform-groups/{group_id}/users", status_code=201)
async def assign_user_to_platform_group(
    group_id: uuid.UUID,
    data: UserAssignment,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.assign_platform_user(group_id, data.user_id)
    await db.commit()
    return {"message": "User assigned to platform group"}


@router.delete(
    "/platform-groups/{group_id}/users/{user_id}",
    status_code=204,
)
async def remove_user_from_platform_group(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.remove_platform_user(group_id, user_id)
    await db.commit()
