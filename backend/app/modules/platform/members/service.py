import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.auth.dependencies import get_effective_permissions
from app.modules.platform.auth.models import (
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.members.schemas import MemberGroupSummary, MemberResponse

# Permissions that indicate "staff" — viewers with these can see member emails
_STAFF_PERMISSIONS = {"org_settings.view", "students.assign", "schedule.substitute"}

MAX_LIMIT = 100


class MemberService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_members(
        self,
        tenant_id: uuid.UUID,
        viewer: User,
        *,
        group_slug: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MemberResponse], int]:
        """List members of a tenant with their groups.

        Uses 2-query strategy to avoid N+1:
        1. Memberships + users (filtered, paginated)
        2. Group assignments for those users (batch)
        """
        limit = min(limit, MAX_LIMIT)

        # Determine if viewer can see emails
        viewer_perms = get_effective_permissions(viewer, tenant_id)
        can_see_emails = bool(viewer_perms & _STAFF_PERMISSIONS) or viewer.is_superadmin

        # --- Query 1: memberships + users ---
        base_query = (
            select(User.id, User.full_name, User.email, User.is_active)
            .join(TenantMembership, TenantMembership.user_id == User.id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active,
            )
        )

        # Filter by group slug
        if group_slug:
            base_query = base_query.where(
                User.id.in_(
                    select(UserGroupAssignment.user_id)
                    .join(PermissionGroup, UserGroupAssignment.group_id == PermissionGroup.id)
                    .where(
                        PermissionGroup.tenant_id == tenant_id,
                        PermissionGroup.slug == group_slug,
                    )
                )
            )

        # Search on name or email
        if search:
            pattern = f"%{search}%"
            base_query = base_query.where(
                User.full_name.ilike(pattern) | User.email.ilike(pattern)
            )

        # Count total (before pagination)
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate + sort
        rows = (
            await self.db.execute(
                base_query
                .order_by(User.full_name.asc(), User.id.asc())
                .limit(limit)
                .offset(offset)
                .distinct()
            )
        ).all()

        if not rows:
            return [], total

        user_ids = [r.id for r in rows]

        # --- Query 2: group assignments for these users ---
        group_rows = (
            await self.db.execute(
                select(
                    UserGroupAssignment.user_id,
                    PermissionGroup.id,
                    PermissionGroup.name,
                    PermissionGroup.slug,
                )
                .join(PermissionGroup, UserGroupAssignment.group_id == PermissionGroup.id)
                .where(
                    UserGroupAssignment.user_id.in_(user_ids),
                    PermissionGroup.tenant_id == tenant_id,
                )
            )
        ).all()

        # Map user_id → groups
        groups_by_user: dict[uuid.UUID, list[MemberGroupSummary]] = defaultdict(list)
        for gr in group_rows:
            groups_by_user[gr.user_id].append(
                MemberGroupSummary(id=gr.id, name=gr.name, slug=gr.slug)
            )

        # Build response
        items = []
        for r in rows:
            # Viewer always sees their own email
            email = r.email if (can_see_emails or r.id == viewer.id) else None
            items.append(
                MemberResponse(
                    user_id=r.id,
                    full_name=r.full_name,
                    email=email,
                    groups=groups_by_user.get(r.id, []),
                    is_active=r.is_active,
                )
            )

        return items, total
