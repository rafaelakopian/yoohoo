"""Collaboration router — tenant-scoped endpoints for managing external collaborators."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.central import get_central_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.invitation.service import InvitationService
from app.modules.platform.auth.models import User
from app.modules.platform.auth.collaboration.schemas import CollaboratorResponse, InviteCollaborator
from app.modules.platform.auth.collaboration.service import CollaborationService
from app.modules.platform.auth.invitation.schemas import InvitationResponse

router = APIRouter(prefix="/collaborations", tags=["collaborations"])


def _get_service(db: AsyncSession = Depends(get_central_db)) -> CollaborationService:
    return CollaborationService(db)


@router.get("/", response_model=list[CollaboratorResponse])
async def list_collaborators(
    request: Request,
    current_user: User = Depends(require_permission("collaborations.view")),
    service: CollaborationService = Depends(_get_service),
):
    """List all external collaborators for this organization."""
    tenant_id = request.state.tenant_id
    return await service.list_collaborators(tenant_id)


@router.post("/invite", response_model=InvitationResponse, status_code=201)
async def invite_collaborator(
    request: Request,
    data: InviteCollaborator,
    current_user: User = Depends(require_permission("collaborations.manage")),
    db: AsyncSession = Depends(get_central_db),
):
    """Invite an external collaborator to this organization."""
    tenant_id = request.state.tenant_id
    collab_service = CollaborationService(db)

    # Determine group: use provided group_id or default to 'medewerker'
    group_id = data.group_id
    if not group_id:
        default_group = await collab_service.get_default_medewerker_group(tenant_id)
        if default_group:
            group_id = default_group.id

    # Validate the group doesn't have admin permissions
    if group_id:
        await collab_service.validate_group_for_collaboration(group_id, tenant_id)

    # Create invitation via existing invitation service
    inv_service = InvitationService(db)
    invitation, _raw_token = await inv_service.create_invitation(
        tenant_id=tenant_id,
        email=data.email,
        role=None,
        inviter=current_user,
        group_id=group_id,
        invitation_type="collaboration",
    )

    # Get group name for response
    group_name = None
    if group_id:
        from sqlalchemy import select
        from app.modules.platform.auth.models import PermissionGroup
        result = await db.execute(
            select(PermissionGroup.name).where(PermissionGroup.id == group_id)
        )
        group_name = result.scalar_one_or_none()

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
        invitation_type=invitation.invitation_type,
    )


@router.put("/{membership_id}/toggle", response_model=CollaboratorResponse)
async def toggle_collaborator(
    request: Request,
    membership_id: uuid.UUID,
    current_user: User = Depends(require_permission("collaborations.manage")),
    service: CollaborationService = Depends(_get_service),
):
    """Activate or deactivate an external collaborator."""
    tenant_id = request.state.tenant_id
    return await service.toggle_collaborator(membership_id, tenant_id)
