import uuid

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.permissions import permission_registry
from app.modules.platform.auth.dependencies import is_platform_user
from app.modules.platform.auth.models import (
    GroupPermission,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)

logger = structlog.get_logger()


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Group CRUD ---

    async def list_groups(self, tenant_id: uuid.UUID) -> list[dict]:
        """List all groups for a tenant with user counts."""
        result = await self.db.execute(
            select(PermissionGroup)
            .options(selectinload(PermissionGroup.permissions))
            .where(PermissionGroup.tenant_id == tenant_id)
            .order_by(PermissionGroup.name)
        )
        groups = result.scalars().all()

        # Get user counts per group
        count_result = await self.db.execute(
            select(
                UserGroupAssignment.group_id,
                func.count(UserGroupAssignment.id).label("user_count"),
            )
            .join(PermissionGroup)
            .where(PermissionGroup.tenant_id == tenant_id)
            .group_by(UserGroupAssignment.group_id)
        )
        counts = {row.group_id: row.user_count for row in count_result}

        return [
            {
                "id": g.id,
                "tenant_id": g.tenant_id,
                "name": g.name,
                "slug": g.slug,
                "description": g.description,
                "is_default": g.is_default,
                "permissions": [p.permission_codename for p in g.permissions],
                "user_count": counts.get(g.id, 0),
                "created_at": g.created_at,
            }
            for g in groups
        ]

    async def get_group(self, group_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
        """Get group detail with permissions."""
        group = await self._get_group(group_id, tenant_id)

        # Count users
        count_result = await self.db.execute(
            select(func.count(UserGroupAssignment.id))
            .where(UserGroupAssignment.group_id == group_id)
        )
        user_count = count_result.scalar() or 0

        return {
            "id": group.id,
            "tenant_id": group.tenant_id,
            "name": group.name,
            "slug": group.slug,
            "description": group.description,
            "is_default": group.is_default,
            "permissions": [p.permission_codename for p in group.permissions],
            "user_count": user_count,
            "created_at": group.created_at,
        }

    async def create_group(
        self, tenant_id: uuid.UUID, name: str, slug: str,
        description: str | None, permissions: list[str],
    ) -> dict:
        """Create a new permission group."""
        # Check slug uniqueness within tenant
        existing = await self.db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id == tenant_id,
                PermissionGroup.slug == slug,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Group with slug '{slug}' already exists")

        # Validate permission codenames
        valid_codenames = permission_registry.get_all_codenames()
        invalid = [p for p in permissions if p not in valid_codenames]
        if invalid:
            raise ValidationError(f"Invalid permission codenames: {', '.join(invalid)}")

        group = PermissionGroup(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            description=description,
            is_default=False,
        )
        self.db.add(group)
        await self.db.flush()

        for codename in permissions:
            gp = GroupPermission(group_id=group.id, permission_codename=codename)
            self.db.add(gp)

        await self.db.flush()
        logger.info("permission_group.created", group_id=str(group.id), slug=slug)

        return await self.get_group(group.id, tenant_id)

    async def update_group(
        self, group_id: uuid.UUID, tenant_id: uuid.UUID,
        name: str | None, description: str | None, permissions: list[str] | None,
    ) -> dict:
        """Update group name, description, or permissions."""
        group = await self._get_group(group_id, tenant_id)

        if name is not None:
            group.name = name
        if description is not None:
            group.description = description

        if permissions is not None:
            # Validate codenames
            valid_codenames = permission_registry.get_all_codenames()
            invalid = [p for p in permissions if p not in valid_codenames]
            if invalid:
                raise ValidationError(f"Invalid permission codenames: {', '.join(invalid)}")

            # Replace all permissions
            await self.db.execute(
                delete(GroupPermission).where(GroupPermission.group_id == group_id)
            )
            for codename in permissions:
                gp = GroupPermission(group_id=group_id, permission_codename=codename)
                self.db.add(gp)

        await self.db.flush()
        # Expire cached permissions so get_group re-loads from DB
        self.db.expire(group, ["permissions"])
        logger.info("permission_group.updated", group_id=str(group_id))

        return await self.get_group(group_id, tenant_id)

    async def delete_group(self, group_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Delete a group. Default groups cannot be deleted."""
        group = await self._get_group(group_id, tenant_id)

        if group.is_default:
            raise ForbiddenError("Default groups cannot be deleted")

        await self.db.delete(group)
        await self.db.flush()
        logger.info("permission_group.deleted", group_id=str(group_id))

    # --- User Assignments ---

    async def list_group_users(self, group_id: uuid.UUID, tenant_id: uuid.UUID) -> list[dict]:
        """List users assigned to a group."""
        await self._get_group(group_id, tenant_id)  # validate access

        result = await self.db.execute(
            select(UserGroupAssignment)
            .options(selectinload(UserGroupAssignment.user))
            .where(UserGroupAssignment.group_id == group_id)
            .order_by(UserGroupAssignment.created_at)
        )
        assignments = result.scalars().all()

        return [
            {
                "user_id": a.user.id,
                "email": a.user.email,
                "full_name": a.user.full_name,
                "assigned_at": a.created_at,
            }
            for a in assignments
        ]

    async def assign_user(
        self, group_id: uuid.UUID, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """Assign a user to a group. Also ensures TenantMembership exists."""
        await self._get_group(group_id, tenant_id)

        # Check user exists
        user = await self.db.execute(select(User).where(User.id == user_id))
        if not user.scalar_one_or_none():
            raise NotFoundError("User", str(user_id))

        # Block platform users from tenant group assignment
        if await is_platform_user(user_id, self.db):
            raise ForbiddenError(
                "Platformgebruikers kunnen niet aan een groep worden toegewezen"
            )

        # Check if already assigned
        existing = await self.db.execute(
            select(UserGroupAssignment).where(
                UserGroupAssignment.user_id == user_id,
                UserGroupAssignment.group_id == group_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("User is already assigned to this group")

        # Ensure TenantMembership exists
        membership = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        if not membership.scalar_one_or_none():
            m = TenantMembership(user_id=user_id, tenant_id=tenant_id, is_active=True)
            self.db.add(m)

        assignment = UserGroupAssignment(user_id=user_id, group_id=group_id)
        self.db.add(assignment)
        await self.db.flush()

        logger.info(
            "permission_group.user_assigned",
            group_id=str(group_id),
            user_id=str(user_id),
        )

    async def remove_user(
        self, group_id: uuid.UUID, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """Remove a user from a group."""
        await self._get_group(group_id, tenant_id)  # validate access

        result = await self.db.execute(
            select(UserGroupAssignment).where(
                UserGroupAssignment.user_id == user_id,
                UserGroupAssignment.group_id == group_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise NotFoundError("UserGroupAssignment", f"{user_id}/{group_id}")

        await self.db.delete(assignment)
        await self.db.flush()

        logger.info(
            "permission_group.user_removed",
            group_id=str(group_id),
            user_id=str(user_id),
        )

    # --- Effective Permissions ---

    async def get_my_permissions(
        self, user: User, tenant_id: uuid.UUID | None
    ) -> dict:
        """Get effective permissions for the current user in the current tenant."""
        from app.modules.platform.auth.dependencies import get_effective_permissions

        effective = get_effective_permissions(user, tenant_id)

        # Get group summaries
        groups = []
        if tenant_id:
            for assignment in user.group_assignments:
                if assignment.group.tenant_id == tenant_id:
                    groups.append({
                        "id": assignment.group.id,
                        "name": assignment.group.name,
                        "slug": assignment.group.slug,
                    })

        return {
            "permissions": sorted(effective),
            "groups": groups,
        }

    # --- Helpers ---

    async def _get_group(
        self, group_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PermissionGroup:
        result = await self.db.execute(
            select(PermissionGroup)
            .options(selectinload(PermissionGroup.permissions))
            .where(
                PermissionGroup.id == group_id,
                PermissionGroup.tenant_id == tenant_id,
            )
        )
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundError("PermissionGroup", str(group_id))
        return group

    # --- Platform Group Methods (tenant_id IS NULL) ---

    async def list_platform_groups(self) -> list[dict]:
        """List all platform-level groups with user counts."""
        result = await self.db.execute(
            select(PermissionGroup)
            .options(selectinload(PermissionGroup.permissions))
            .where(PermissionGroup.tenant_id.is_(None))
            .order_by(PermissionGroup.name)
        )
        groups = result.scalars().all()

        count_result = await self.db.execute(
            select(
                UserGroupAssignment.group_id,
                func.count(UserGroupAssignment.id).label("user_count"),
            )
            .join(PermissionGroup)
            .where(PermissionGroup.tenant_id.is_(None))
            .group_by(UserGroupAssignment.group_id)
        )
        counts = {row.group_id: row.user_count for row in count_result}

        return [
            {
                "id": g.id,
                "tenant_id": None,
                "name": g.name,
                "slug": g.slug,
                "description": g.description,
                "is_default": g.is_default,
                "permissions": [p.permission_codename for p in g.permissions],
                "user_count": counts.get(g.id, 0),
                "created_at": g.created_at,
            }
            for g in groups
        ]

    async def get_platform_group(self, group_id: uuid.UUID) -> dict:
        """Get platform group detail with permissions."""
        group = await self._get_platform_group(group_id)

        count_result = await self.db.execute(
            select(func.count(UserGroupAssignment.id))
            .where(UserGroupAssignment.group_id == group_id)
        )
        user_count = count_result.scalar() or 0

        return {
            "id": group.id,
            "tenant_id": None,
            "name": group.name,
            "slug": group.slug,
            "description": group.description,
            "is_default": group.is_default,
            "permissions": [p.permission_codename for p in group.permissions],
            "user_count": user_count,
            "created_at": group.created_at,
        }

    async def create_platform_group(
        self, name: str, slug: str,
        description: str | None, permissions: list[str],
    ) -> dict:
        """Create a new platform-level permission group."""
        existing = await self.db.execute(
            select(PermissionGroup).where(
                PermissionGroup.tenant_id.is_(None),
                PermissionGroup.slug == slug,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Platform group with slug '{slug}' already exists")

        valid_codenames = permission_registry.get_all_codenames()
        invalid = [p for p in permissions if p not in valid_codenames]
        if invalid:
            raise ValidationError(f"Invalid permission codenames: {', '.join(invalid)}")

        group = PermissionGroup(
            tenant_id=None,
            name=name,
            slug=slug,
            description=description,
            is_default=False,
        )
        self.db.add(group)
        await self.db.flush()

        for codename in permissions:
            gp = GroupPermission(group_id=group.id, permission_codename=codename)
            self.db.add(gp)

        await self.db.flush()
        logger.info("platform_group.created", group_id=str(group.id), slug=slug)

        return await self.get_platform_group(group.id)

    async def update_platform_group(
        self, group_id: uuid.UUID,
        name: str | None, description: str | None, permissions: list[str] | None,
    ) -> dict:
        """Update a platform group."""
        group = await self._get_platform_group(group_id)

        if name is not None:
            group.name = name
        if description is not None:
            group.description = description

        if permissions is not None:
            valid_codenames = permission_registry.get_all_codenames()
            invalid = [p for p in permissions if p not in valid_codenames]
            if invalid:
                raise ValidationError(f"Invalid permission codenames: {', '.join(invalid)}")

            await self.db.execute(
                delete(GroupPermission).where(GroupPermission.group_id == group_id)
            )
            for codename in permissions:
                gp = GroupPermission(group_id=group_id, permission_codename=codename)
                self.db.add(gp)

        await self.db.flush()
        self.db.expire(group, ["permissions"])
        logger.info("platform_group.updated", group_id=str(group_id))

        return await self.get_platform_group(group_id)

    async def delete_platform_group(self, group_id: uuid.UUID) -> None:
        """Delete a platform group. Default groups cannot be deleted."""
        group = await self._get_platform_group(group_id)

        if group.is_default:
            raise ForbiddenError("Default groups cannot be deleted")

        await self.db.delete(group)
        await self.db.flush()
        logger.info("platform_group.deleted", group_id=str(group_id))

    async def list_platform_group_users(self, group_id: uuid.UUID) -> list[dict]:
        """List users assigned to a platform group."""
        await self._get_platform_group(group_id)

        result = await self.db.execute(
            select(UserGroupAssignment)
            .options(selectinload(UserGroupAssignment.user))
            .where(UserGroupAssignment.group_id == group_id)
            .order_by(UserGroupAssignment.created_at)
        )
        assignments = result.scalars().all()

        return [
            {
                "user_id": a.user.id,
                "email": a.user.email,
                "full_name": a.user.full_name,
                "assigned_at": a.created_at,
            }
            for a in assignments
        ]

    async def assign_platform_user(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Assign a user to a platform group (no TenantMembership needed)."""
        await self._get_platform_group(group_id)

        user = await self.db.execute(select(User).where(User.id == user_id))
        if not user.scalar_one_or_none():
            raise NotFoundError("User", str(user_id))

        existing = await self.db.execute(
            select(UserGroupAssignment).where(
                UserGroupAssignment.user_id == user_id,
                UserGroupAssignment.group_id == group_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("User is already assigned to this group")

        assignment = UserGroupAssignment(user_id=user_id, group_id=group_id)
        self.db.add(assignment)
        await self.db.flush()

        logger.info(
            "platform_group.user_assigned",
            group_id=str(group_id),
            user_id=str(user_id),
        )

    async def remove_platform_user(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Remove a user from a platform group."""
        await self._get_platform_group(group_id)

        result = await self.db.execute(
            select(UserGroupAssignment).where(
                UserGroupAssignment.user_id == user_id,
                UserGroupAssignment.group_id == group_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise NotFoundError("UserGroupAssignment", f"{user_id}/{group_id}")

        await self.db.delete(assignment)
        await self.db.flush()

        logger.info(
            "platform_group.user_removed",
            group_id=str(group_id),
            user_id=str(user_id),
        )

    async def _get_platform_group(self, group_id: uuid.UUID) -> PermissionGroup:
        """Get a platform-level group by ID."""
        result = await self.db.execute(
            select(PermissionGroup)
            .options(selectinload(PermissionGroup.permissions))
            .where(
                PermissionGroup.id == group_id,
                PermissionGroup.tenant_id.is_(None),
            )
        )
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundError("PermissionGroup", str(group_id))
        return group
