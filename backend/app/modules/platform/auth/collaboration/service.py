"""Service for managing collaborations (external teachers)."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.platform.auth.core.schemas import GroupSummary
from app.modules.platform.auth.models import (
    GroupPermission,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.auth.collaboration.schemas import CollaboratorResponse

logger = structlog.get_logger()

# Permissions that a collaborator group must NOT have (security boundary)
FORBIDDEN_COLLAB_PERMISSIONS = {
    "org_settings.view",
    "org_settings.edit",
    "collaborations.manage",
    "invitations.manage",
}


class CollaborationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_collaborators(self, tenant_id: uuid.UUID) -> list[CollaboratorResponse]:
        """List all collaboration memberships for a tenant."""
        result = await self.db.execute(
            select(TenantMembership, User)
            .join(User, User.id == TenantMembership.user_id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.membership_type == "collaboration",
            )
            .order_by(TenantMembership.created_at.desc())
        )

        collaborators = []
        for membership, user in result.all():
            # Fetch groups for this user in this tenant
            group_result = await self.db.execute(
                select(PermissionGroup)
                .join(UserGroupAssignment, UserGroupAssignment.group_id == PermissionGroup.id)
                .where(
                    UserGroupAssignment.user_id == user.id,
                    PermissionGroup.tenant_id == tenant_id,
                )
            )
            groups = [
                GroupSummary(id=g.id, name=g.name, slug=g.slug)
                for g in group_result.scalars().all()
            ]

            collaborators.append(CollaboratorResponse(
                membership_id=membership.id,
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=membership.is_active,
                groups=groups,
                created_at=membership.created_at,
            ))

        return collaborators

    async def toggle_collaborator(
        self, membership_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> CollaboratorResponse:
        """Toggle is_active on a collaboration membership."""
        result = await self.db.execute(
            select(TenantMembership, User)
            .join(User, User.id == TenantMembership.user_id)
            .where(
                TenantMembership.id == membership_id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.membership_type == "collaboration",
            )
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundError("Collaboration membership", str(membership_id))

        membership, user = row
        membership.is_active = not membership.is_active
        await self.db.flush()

        # Fetch groups
        group_result = await self.db.execute(
            select(PermissionGroup)
            .join(UserGroupAssignment, UserGroupAssignment.group_id == PermissionGroup.id)
            .where(
                UserGroupAssignment.user_id == user.id,
                PermissionGroup.tenant_id == tenant_id,
            )
        )
        groups = [
            GroupSummary(id=g.id, name=g.name, slug=g.slug)
            for g in group_result.scalars().all()
        ]

        logger.info(
            "collaboration.toggled",
            membership_id=str(membership_id),
            is_active=membership.is_active,
        )

        return CollaboratorResponse(
            membership_id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=membership.is_active,
            groups=groups,
            created_at=membership.created_at,
        )

    async def validate_group_for_collaboration(
        self, group_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PermissionGroup:
        """Validate a group is suitable for a collaborator (no admin permissions)."""
        result = await self.db.execute(
            select(PermissionGroup).where(
                PermissionGroup.id == group_id,
                PermissionGroup.tenant_id == tenant_id,
            )
        )
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundError("PermissionGroup", str(group_id))

        # Check the group doesn't contain forbidden permissions
        perm_result = await self.db.execute(
            select(GroupPermission.permission_codename).where(
                GroupPermission.group_id == group_id
            )
        )
        codenames = set(perm_result.scalars().all())
        forbidden = codenames & FORBIDDEN_COLLAB_PERMISSIONS
        if forbidden:
            raise ForbiddenError(
                f"Deze groep bevat beheerdersrechten en kan niet worden gebruikt voor samenwerkingen: {', '.join(sorted(forbidden))}"
            )

        return group

    async def get_default_medewerker_group(self, tenant_id: uuid.UUID) -> PermissionGroup | None:
        """Get the default 'medewerker' group for a tenant."""
        result = await self.db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id == tenant_id,
                PermissionGroup.slug == "medewerker",
            )
        )
        return result.scalar_one_or_none()
