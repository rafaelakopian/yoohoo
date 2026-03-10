"""Invitation router -- split into org-scoped and auth-scoped endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import get_client_ip
from app.core.rate_limiter import rate_limit
from app.db.central import get_central_db
from app.modules.platform.auth.core.schemas import MessageResponse
from app.modules.platform.auth.dependencies import get_current_user_optional, require_permission
from app.modules.platform.auth.models import User
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

# Org-scoped router (mounted under tenant_parent: /org/{slug}/access/invitations)
org_router = APIRouter(prefix="/access/invitations", tags=["invitations"])


@org_router.post(
    "",
    response_model=InvitationResponse,
    status_code=201,
)
async def create_invitation(
    request: Request,
    data: CreateInvitation,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    tenant_id = request.state.tenant_id
    service = InvitationService(db)
    invitation, _ = await service.create_invitation(
        tenant_id, data.email, current_user, group_id=data.group_id
    )
    # Build response with inviter name
    group_name = None
    if invitation.group and hasattr(invitation.group, "name"):
        group_name = invitation.group.name
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        group_id=invitation.group_id,
        group_name=group_name,
        tenant_id=invitation.tenant_id,
        invited_by_name=current_user.full_name,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@org_router.get(
    "",
    response_model=list[InvitationWithStatus],
)
async def list_invitations(
    request: Request,
    status: str | None = Query(None, pattern="^(pending|accepted|revoked|expired)$"),
    current_user: User = Depends(require_permission("invitations.view", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    tenant_id = request.state.tenant_id
    service = InvitationService(db)
    return await service.list_invitations(tenant_id, status=status)


@org_router.post(
    "/bulk",
    response_model=BulkInvitationResponse,
    status_code=200,
)
async def create_bulk_invitations(
    request: Request,
    data: CreateBulkInvitations,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    tenant_id = request.state.tenant_id
    service = InvitationService(db)
    return await service.create_bulk_invitations(
        tenant_id, data.emails, current_user, group_id=data.group_id
    )


@org_router.post(
    "/{invitation_id}/resend",
    response_model=MessageResponse,
)
async def resend_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    tenant_id = request.state.tenant_id
    service = InvitationService(db)
    await service.resend_invitation(invitation_id, tenant_id, current_user)
    return MessageResponse(message="Uitnodiging opnieuw verstuurd")


@org_router.delete(
    "/{invitation_id}",
    response_model=MessageResponse,
)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("invitations.manage", hidden=True)),
    db: AsyncSession = Depends(get_central_db),
):
    tenant_id = request.state.tenant_id
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
    request: Request,
    # secrets.token_urlsafe(32) generates 43-char strings; 20 catches empty/trivial tokens
    token: str = Query(..., min_length=20),
    db: AsyncSession = Depends(get_central_db),
):
    service = InvitationService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    return await service.get_invite_info(token, ip_address=ip, user_agent=ua)


@auth_router.post(
    "/accept-invite",
    response_model=AcceptInvitationResponse,
    dependencies=[Depends(rate_limit(5, 3600, key_prefix="rl:accept-invite"))],
)
async def accept_invite(
    data: AcceptInvitation,
    request: Request,
    db: AsyncSession = Depends(get_central_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    service = InvitationService(db)
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    return await service.accept_invitation(
        data.token, data.password, data.full_name,
        ip_address=ip, user_agent=ua,
        current_user=current_user,
    )
