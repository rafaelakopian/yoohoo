import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.platform.admin.schemas import (
    AddMembership,
    AdminTenantDetail,
    AdminUserDetail,
    PaginatedAuditLogs,
    PlatformInviteRequest,
    PlatformStaffItem,
    PlatformStats,
    SuperAdminToggle,
    TransferOwnership,
    UserSearchResult,
)
from app.modules.platform.admin.service import AdminService
from app.modules.platform.auth.invitation.service import InvitationService
from app.modules.platform.auth.permissions.service import PermissionService
from app.modules.platform.auth.permissions.schemas import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    GroupUserResponse,
    UserAssignment,
)

router = APIRouter(prefix="/platform", tags=["platform-admin"])


async def get_admin_service(
    db: AsyncSession = Depends(get_central_db),
) -> AdminService:
    return AdminService(db)


async def get_permission_service(
    db: AsyncSession = Depends(get_central_db),
) -> PermissionService:
    return PermissionService(db)


@router.get("/dashboard", response_model=PlatformStats)
async def get_platform_stats(
    _: User = Depends(require_permission("platform.view_stats")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_platform_stats()


@router.get("/orgs/{tenant_id}/detail", response_model=AdminTenantDetail)
async def get_tenant_detail(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.view_orgs")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_tenant_detail(tenant_id)


@router.put("/access/users/{user_id}/superadmin")
async def toggle_superadmin(
    user_id: uuid.UUID,
    body: SuperAdminToggle,
    current_user: User = Depends(require_permission("platform.manage_superadmin")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.toggle_superadmin(user_id, body.is_superadmin, current_user_id=current_user.id)


@router.get("/access/users", response_model=list[PlatformStaffItem])
async def list_platform_users(
    _: User = Depends(require_permission("platform.view_users")),
    service: AdminService = Depends(get_admin_service),
):
    """Lijst alle gebruikers met platform-toegang."""
    return await service.list_platform_users()


@router.get("/access/users/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=2, max_length=100),
    _: User = Depends(require_permission("platform.view_users")),
    service: AdminService = Depends(get_admin_service),
):
    """Zoek users op email of naam voor groep-toewijzing."""
    return await service.search_user_by_email(q)


@router.post(
    "/access/users/invite",
    dependencies=[Depends(rate_limit(5, 3600, key_prefix="rl:platform-invite"))],
)
async def invite_platform_user(
    data: PlatformInviteRequest,
    current_user: User = Depends(require_permission("platform.manage_superadmin")),
    db: AsyncSession = Depends(get_central_db),
):
    """Invite a user to the platform. Sends an invitation link via email."""
    service = InvitationService(db)
    result = await service.create_platform_invitation(
        email=data.email,
        inviter=current_user,
    )
    await db.commit()
    return result


@router.put("/orgs/{tenant_id}/owner")
async def transfer_ownership(
    tenant_id: uuid.UUID,
    body: TransferOwnership,
    current_user: User = Depends(require_permission("platform.manage_orgs")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.transfer_ownership(
        tenant_id, body.user_id, current_user_id=current_user.id,
    )


@router.post("/orgs/{tenant_id}/memberships")
async def add_membership(
    tenant_id: uuid.UUID,
    body: AddMembership,
    _: User = Depends(require_permission("platform.manage_memberships")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.add_membership(tenant_id, body.user_id, group_id=body.group_id)


@router.delete("/orgs/{tenant_id}/memberships/{user_id}", status_code=204)
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
    category: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await service.list_audit_logs(
        user_id=user_id, action=action, category=category,
        date_from=date_from, date_to=date_to,
        skip=skip, limit=limit,
    )


# --- Permission Groups per Tenant ---


@router.get("/orgs/{tenant_id}/groups", response_model=list[GroupResponse])
async def admin_list_groups(
    tenant_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_groups(tenant_id)


@router.post("/orgs/{tenant_id}/groups", response_model=GroupResponse, status_code=201)
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


@router.get("/orgs/{tenant_id}/groups/{group_id}", response_model=GroupResponse)
async def admin_get_group(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.get_group(group_id, tenant_id)


@router.put("/orgs/{tenant_id}/groups/{group_id}", response_model=GroupResponse)
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


@router.delete("/orgs/{tenant_id}/groups/{group_id}", status_code=204)
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
    "/orgs/{tenant_id}/groups/{group_id}/users",
    response_model=list[GroupUserResponse],
)
async def admin_list_group_users(
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_group_users(group_id, tenant_id)


@router.post("/orgs/{tenant_id}/groups/{group_id}/users", status_code=201)
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
    "/orgs/{tenant_id}/groups/{group_id}/users/{user_id}",
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


@router.get("/access/groups", response_model=list[GroupResponse])
async def list_platform_groups(
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_platform_groups()


@router.post("/access/groups", response_model=GroupResponse, status_code=201)
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


@router.get("/access/groups/{group_id}", response_model=GroupResponse)
async def get_platform_group(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.get_platform_group(group_id)


@router.put("/access/groups/{group_id}", response_model=GroupResponse)
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


@router.delete("/access/groups/{group_id}", status_code=204)
async def delete_platform_group(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_central_db),
):
    await service.delete_platform_group(group_id)
    await db.commit()


@router.get(
    "/access/groups/{group_id}/users",
    response_model=list[GroupUserResponse],
)
async def list_platform_group_users(
    group_id: uuid.UUID,
    _: User = Depends(require_permission("platform.manage_groups")),
    service: PermissionService = Depends(get_permission_service),
):
    return await service.list_platform_group_users(group_id)


@router.post("/access/groups/{group_id}/users", status_code=201)
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
    "/access/groups/{group_id}/users/{user_id}",
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


# --- Account Archive / Reactivation ---


@router.post("/access/users/{user_id}/reactivate", response_model=AdminUserDetail)
async def reactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("platform.edit_users")),
    service: AdminService = Depends(get_admin_service),
):
    return await service.reactivate_archived_account(user_id, current_user)
