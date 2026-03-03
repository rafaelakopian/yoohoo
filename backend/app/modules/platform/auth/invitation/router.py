"""Invitation router — split into school-scoped and auth-scoped endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.invitation.schemas import (
    AcceptInvitation,
    AcceptInvitationResponse,
    BulkInvitationResponse,
    CreateBulkInvitations,
    CreateInvitation,
    InvitationResponse,
    InvitationWithStatus,
    InviteInfo,
)
from app.modules.platform.auth.invitation.service import InvitationService
from app.modules.platform.auth.models import TenantMembership, User


async def _verify_tenant_access(
    user: User, tenant_id: uuid.UUID, db: AsyncSession
) -> None:
    """Verify user is superadmin or has an active membership for this tenant."""
    if user.is_superadmin:
        return
    result = await db.execute(
        select(TenantMembership.id).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Not found")

# School-scoped router (mounted under /schools/{tenant_id}/invitations)
school_router = APIRouter(tags=["invitations"])


@school_router.post(
    "/schools/{tenant_id}/invitations",
    response_model=InvitationResponse,
    status_code=201,
)
async def create_invitation(
    tenant_id: uuid.UUID,
    data: CreateInvitation,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    await _verify_tenant_access(current_user, tenant_id, db)
    service = InvitationService(db)
    invitation, _ = await service.create_invitation(
        tenant_id, data.email, data.role, current_user, group_id=data.group_id
    )
    # Build response with inviter name
    group_name = None
    if invitation.group and hasattr(invitation.group, "name"):
        group_name = invitation.group.name
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        group_id=invitation.group_id,
        group_name=group_name,
        tenant_id=invitation.tenant_id,
        invited_by_name=current_user.full_name,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@school_router.get(
    "/schools/{tenant_id}/invitations",
    response_model=list[InvitationWithStatus],
)
async def list_invitations(
    tenant_id: uuid.UUID,
    status: str | None = Query(None, pattern="^(pending|accepted|revoked|expired)$"),
    current_user: User = Depends(require_permission("invitations.view", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    await _verify_tenant_access(current_user, tenant_id, db)
    service = InvitationService(db)
    return await service.list_invitations(tenant_id, status=status)


@school_router.post(
    "/schools/{tenant_id}/invitations/bulk",
    response_model=BulkInvitationResponse,
    status_code=200,
)
async def create_bulk_invitations(
    tenant_id: uuid.UUID,
    data: CreateBulkInvitations,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    await _verify_tenant_access(current_user, tenant_id, db)
    service = InvitationService(db)
    return await service.create_bulk_invitations(
        tenant_id, data.emails, current_user, group_id=data.group_id
    )


@school_router.post(
    "/schools/{tenant_id}/invitations/{invitation_id}/resend",
    response_model=MessageResponse,
)
async def resend_invitation(
    tenant_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    await _verify_tenant_access(current_user, tenant_id, db)
    service = InvitationService(db)
    await service.resend_invitation(invitation_id, tenant_id, current_user)
    return MessageResponse(message="Uitnodiging opnieuw verstuurd")


@school_router.delete(
    "/schools/{tenant_id}/invitations/{invitation_id}",
    response_model=MessageResponse,
)
async def revoke_invitation(
    tenant_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    await _verify_tenant_access(current_user, tenant_id, db)
    service = InvitationService(db)
    await service.revoke_invitation(invitation_id, tenant_id, current_user)
    return MessageResponse(message="Uitnodiging ingetrokken")


# Auth-scoped router (mounted under /auth/)
auth_router = APIRouter(prefix="/auth", tags=["auth-invitations"])


@auth_router.get(
    "/invite-info",
    response_model=InviteInfo,
    dependencies=[Depends(rate_limit(10, 300, key_prefix="rl:invite-info"))],
)
async def get_invite_info(
    token: str = Query(...),
    db: AsyncSession = Depends(get_central_db),
):
    service = InvitationService(db)
    return await service.get_invite_info(token)


@auth_router.post(
    "/accept-invite",
    response_model=AcceptInvitationResponse,
    dependencies=[Depends(rate_limit(5, 3600, key_prefix="rl:accept-invite"))],
)
async def accept_invite(
    data: AcceptInvitation,
    db: AsyncSession = Depends(get_central_db),
):
    service = InvitationService(db)
    return await service.accept_invitation(
        data.token, data.password, data.full_name
    )
