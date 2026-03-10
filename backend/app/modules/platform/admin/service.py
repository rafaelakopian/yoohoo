import uuid
from datetime import datetime

import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.dependencies import is_platform_user
from app.modules.platform.auth.models import (
    AuditLog,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
)
from app.modules.platform.billing.models import (
    PlanInterval,
    PlatformPlan,
    PlatformSubscription,
    SubscriptionStatus,
)
from app.modules.platform.tenant_mgmt.models import Tenant

logger = structlog.get_logger()


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_platform_stats(self) -> dict:
        tenant_counts = await self.db.execute(
            select(
                func.count(Tenant.id).label("total"),
                func.count(Tenant.id).filter(Tenant.is_active).label("active"),
                func.count(Tenant.id).filter(Tenant.is_provisioned).label("provisioned"),
            )
        )
        row = tenant_counts.one()

        # Active subscriptions + MRR
        from sqlalchemy import case

        monthly_price = case(
            (PlatformPlan.interval == PlanInterval.yearly, PlatformPlan.price_cents / 12),
            else_=PlatformPlan.price_cents,
        )
        sub_result = await self.db.execute(
            select(
                func.count(PlatformSubscription.id).label("count"),
                func.coalesce(func.sum(monthly_price), 0).label("mrr"),
            )
            .join(PlatformPlan, PlatformSubscription.plan_id == PlatformPlan.id)
            .where(
                PlatformSubscription.status.in_([
                    SubscriptionStatus.active,
                    SubscriptionStatus.past_due,
                    SubscriptionStatus.trialing,
                ])
            )
        )
        sub_row = sub_result.one()
        active_subscriptions = sub_row.count
        mrr_cents = int(sub_row.mrr)

        # Platform user IDs: superadmins + users in platform groups (tenant_id IS NULL)
        platform_user_ids = (
            select(User.id).where(User.is_superadmin.is_(True))
            .union(
                select(UserGroupAssignment.user_id)
                .join(PermissionGroup, UserGroupAssignment.group_id == PermissionGroup.id)
                .where(PermissionGroup.tenant_id.is_(None))
            )
        ).subquery()

        # Count org users (excluding platform users)
        user_counts = await self.db.execute(
            select(
                func.count(User.id).label("total"),
                func.count(User.id).filter(User.is_active).label("active"),
            ).where(User.id.not_in(select(platform_user_ids.c.id)))
        )
        urow = user_counts.one()

        # Count platform users
        platform_user_count_result = await self.db.execute(
            select(func.count()).select_from(platform_user_ids)
        )
        platform_user_count = platform_user_count_result.scalar() or 0

        # Count platform groups
        platform_group_count_result = await self.db.execute(
            select(func.count(PermissionGroup.id)).where(
                PermissionGroup.tenant_id.is_(None)
            )
        )
        platform_group_count = platform_group_count_result.scalar() or 0

        return {
            "total_tenants": row.total,
            "active_tenants": row.active,
            "provisioned_tenants": row.provisioned,
            "active_subscriptions": active_subscriptions,
            "mrr_cents": mrr_cents,
            "total_users": urow.total,
            "active_users": urow.active,
            "platform_user_count": platform_user_count,
            "platform_group_count": platform_group_count,
        }

    async def list_tenants_admin(self) -> list[dict]:
        # Get tenants with owner name and member count
        result = await self.db.execute(
            select(Tenant)
            .options(
                selectinload(Tenant.memberships).selectinload(TenantMembership.user),
            )
            .order_by(Tenant.name)
        )
        tenants = result.scalars().all()

        items = []
        for t in tenants:
            # Get owner name
            owner_name = None
            if t.owner_id:
                owner = await self.db.execute(
                    select(User.full_name).where(User.id == t.owner_id)
                )
                owner_row = owner.scalar_one_or_none()
                owner_name = owner_row

            # Exclude platform users (superadmins) from member count
            real_members = [m for m in t.memberships if not m.user.is_superadmin]

            items.append({
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "is_active": t.is_active,
                "is_provisioned": t.is_provisioned,
                "owner_name": owner_name,
                "member_count": len(real_members),
                "created_at": t.created_at,
            })

        return items

    async def get_tenant_detail(self, tenant_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(Tenant)
            .options(
                selectinload(Tenant.memberships).selectinload(TenantMembership.user),
                selectinload(Tenant.settings),
            )
            .where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", str(tenant_id))

        # Get owner name
        owner_name = None
        if tenant.owner_id:
            owner = await self.db.execute(
                select(User.full_name).where(User.id == tenant.owner_id)
            )
            owner_name = owner.scalar_one_or_none()

        # Build settings dict
        settings_dict = None
        if tenant.settings:
            settings_dict = {
                "org_name": tenant.settings.org_name,
                "org_address": tenant.settings.org_address,
                "org_phone": tenant.settings.org_phone,
                "org_email": tenant.settings.org_email,
                "timezone": tenant.settings.timezone,
                "academic_year_start_month": tenant.settings.academic_year_start_month,
            }

        # Get group assignments for all users in this tenant
        group_result = await self.db.execute(
            select(UserGroupAssignment)
            .join(PermissionGroup)
            .options(selectinload(UserGroupAssignment.group))
            .where(PermissionGroup.tenant_id == tenant_id)
        )
        all_assignments = group_result.scalars().all()
        user_groups: dict[uuid.UUID, list[dict]] = {}
        for a in all_assignments:
            user_groups.setdefault(a.user_id, []).append({
                "id": a.group.id,
                "name": a.group.name,
                "slug": a.group.slug,
            })

        # Exclude platform users (superadmins) from memberships
        real_memberships = [m for m in tenant.memberships if not m.user.is_superadmin]

        memberships = [
            {
                "user_id": m.user_id,
                "email": m.user.email,
                "full_name": m.user.full_name,
                "is_active": m.is_active,
                "groups": user_groups.get(m.user_id, []),
            }
            for m in real_memberships
        ]

        return {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "is_active": tenant.is_active,
            "is_provisioned": tenant.is_provisioned,
            "owner_name": owner_name,
            "member_count": len(real_memberships),
            "created_at": tenant.created_at,
            "settings": settings_dict,
            "memberships": memberships,
        }

    async def get_user_detail(self, user_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.memberships).selectinload(TenantMembership.tenant),
                selectinload(User.group_assignments)
                .selectinload(UserGroupAssignment.group),
            )
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        # Build groups per tenant
        tenant_groups: dict[uuid.UUID, list[dict]] = {}
        for a in user.group_assignments:
            tenant_groups.setdefault(a.group.tenant_id, []).append({
                "id": a.group.id,
                "name": a.group.name,
                "slug": a.group.slug,
            })

        memberships = [
            {
                "tenant_id": m.tenant_id,
                "tenant_name": m.tenant.name,
                "tenant_slug": m.tenant.slug,
                "is_active": m.is_active,
                "groups": tenant_groups.get(m.tenant_id, []),
            }
            for m in user.memberships
        ]

        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superadmin": user.is_superadmin,
            "email_verified": user.email_verified,
            "totp_enabled": user.totp_enabled,
            "membership_count": len(user.memberships),
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "memberships": memberships,
        }

    async def list_audit_logs(
        self,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        category: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """List audit logs with optional filters. Joins User for email."""
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            escaped_action = action.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(AuditLog.action.ilike(f"%{escaped_action}%"))
        if category:
            escaped_cat = category.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(AuditLog.action.ilike(f"{escaped_cat}.%"))
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at <= date_to)

        # Total count
        count_query = select(func.count(AuditLog.id))
        for f in filters:
            count_query = count_query.where(f)
        total = (await self.db.execute(count_query)).scalar() or 0

        # Data query with LEFT JOIN on User for email
        query = (
            select(AuditLog, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
        )
        for f in filters:
            query = query.where(f)
        query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            {
                "id": row[0].id,
                "user_id": row[0].user_id,
                "user_email": row[1],
                "action": row[0].action,
                "ip_address": row[0].ip_address,
                "details": row[0].details,
                "created_at": row[0].created_at,
            }
            for row in rows
        ]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def toggle_superadmin(
        self, user_id: uuid.UUID, is_superadmin: bool, current_user_id: uuid.UUID,
    ) -> dict:
        # Self-protection: you cannot remove your own superadmin status
        if user_id == current_user_id and not is_superadmin:
            raise ForbiddenError("Je kunt je eigen superadmin-status niet ontnemen")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        # Last-superadmin protection: cannot remove the only superadmin
        if not is_superadmin and user.is_superadmin:
            count_result = await self.db.execute(
                select(func.count(User.id)).where(User.is_superadmin.is_(True))
            )
            if (count_result.scalar() or 0) <= 1:
                raise ForbiddenError("De laatste superadmin kan niet worden verwijderd")

        # When promoting to superadmin: cleanup tenant memberships + tenant group assignments
        memberships_removed = 0
        groups_removed = 0
        if is_superadmin and not user.is_superadmin:
            # Remove all TenantMemberships
            del_result = await self.db.execute(
                delete(TenantMembership).where(TenantMembership.user_id == user_id)
            )
            memberships_removed = del_result.rowcount

            # Remove tenant group assignments (keep platform groups)
            tenant_assignments = await self.db.execute(
                select(UserGroupAssignment)
                .join(PermissionGroup)
                .where(
                    UserGroupAssignment.user_id == user_id,
                    PermissionGroup.tenant_id != None,  # noqa: E711
                )
            )
            for a in tenant_assignments.scalars().all():
                await self.db.delete(a)
                groups_removed += 1

            await self.db.flush()

            audit = AuditService(self.db)
            await audit.log(
                "superadmin.promoted",
                user_id=user_id,
                actor_id=str(current_user_id),
                memberships_removed=memberships_removed,
                tenant_groups_removed=groups_removed,
            )
            logger.info(
                "superadmin.promoted.cleanup",
                user_id=str(user_id),
                memberships_removed=memberships_removed,
                tenant_groups_removed=groups_removed,
            )

        user.is_superadmin = is_superadmin
        await self.db.flush()

        return {"id": user.id, "is_superadmin": user.is_superadmin}

    async def search_user_by_email(self, query: str, limit: int = 10) -> list[dict]:
        """
        Zoekt users op email of naam (ILIKE, min 2 tekens).
        Bedoeld voor platform groep-toewijzing — retourneert minimale data.
        """
        if len(query) < 2:
            return []

        escaped = (
            query
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        search_filter = f"%{escaped}%"

        result = await self.db.execute(
            select(User)
            .where(
                User.is_active.is_(True),
                or_(
                    User.email.ilike(search_filter),
                    User.full_name.ilike(search_filter),
                ),
            )
            .order_by(User.email)
            .limit(limit)
        )
        users = result.scalars().all()
        return [
            {"id": user.id, "email": user.email, "full_name": user.full_name}
            for user in users
        ]

    async def list_platform_users(self) -> list[dict]:
        """
        Retourneert alle gebruikers met platform-toegang:
        - is_superadmin = True
        - OF heeft een UserGroupAssignment naar een PermissionGroup
          met tenant_id IS NULL
        """
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.group_assignments).selectinload(
                    UserGroupAssignment.group
                )
            )
            .where(
                or_(
                    User.is_superadmin.is_(True),
                    User.id.in_(
                        select(UserGroupAssignment.user_id).join(
                            PermissionGroup,
                            UserGroupAssignment.group_id == PermissionGroup.id,
                        ).where(PermissionGroup.tenant_id.is_(None))
                    ),
                )
            )
            .order_by(User.full_name)
        )
        users = result.scalars().unique().all()

        items = []
        for user in users:
            platform_groups = [
                {
                    "id": str(a.group.id),
                    "name": a.group.name,
                    "slug": a.group.slug,
                }
                for a in user.group_assignments
                if a.group.tenant_id is None
            ]
            items.append({
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_superadmin": user.is_superadmin,
                "platform_groups": platform_groups,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
            })
        return items

    async def add_membership(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID,
        group_id: uuid.UUID | None = None,
    ) -> dict:
        # Verify tenant exists
        tenant = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        if not tenant.scalar_one_or_none():
            raise NotFoundError("Tenant", str(tenant_id))

        # Verify user exists
        user = await self.db.execute(select(User).where(User.id == user_id))
        if not user.scalar_one_or_none():
            raise NotFoundError("User", str(user_id))

        # Block platform users from getting tenant memberships
        if await is_platform_user(user_id, self.db):
            raise ForbiddenError(
                "Platformgebruikers kunnen niet als lid worden toegevoegd"
            )

        # Verify group if provided
        if group_id:
            group = await self.db.execute(
                select(PermissionGroup).where(
                    PermissionGroup.id == group_id,
                    PermissionGroup.tenant_id == tenant_id,
                )
            )
            if not group.scalar_one_or_none():
                raise NotFoundError("PermissionGroup", str(group_id))

        # Check for existing membership
        existing = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("User already has a membership for this tenant")

        membership = TenantMembership(
            user_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(membership)
        await self.db.flush()

        # Create group assignment if group_id provided
        if group_id:
            assignment = UserGroupAssignment(
                user_id=user_id,
                group_id=group_id,
            )
            self.db.add(assignment)
            await self.db.flush()

        return {
            "id": membership.id,
            "user_id": membership.user_id,
            "tenant_id": membership.tenant_id,
            "is_active": membership.is_active,
        }

    async def transfer_ownership(
        self,
        tenant_id: uuid.UUID,
        new_owner_id: uuid.UUID | None,
        current_user_id: uuid.UUID,
    ) -> dict:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", str(tenant_id))

        old_owner_id = tenant.owner_id

        if new_owner_id:
            # Verify user exists
            user_result = await self.db.execute(
                select(User).where(User.id == new_owner_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise NotFoundError("User", str(new_owner_id))

            # Block platform users from being tenant owners
            if await is_platform_user(new_owner_id, self.db):
                raise ForbiddenError(
                    "Platformgebruikers kunnen geen eigenaar van een organisatie zijn"
                )

            # Verify user is a member of this tenant
            membership = await self.db.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.user_id == new_owner_id,
                )
            )
            if not membership.scalar_one_or_none():
                raise ForbiddenError(
                    "Gebruiker moet lid zijn van de organisatie om eigenaar te worden"
                )

        tenant.owner_id = new_owner_id
        await self.db.flush()

        # Audit log
        audit = AuditService(self.db)
        await audit.log(
            "tenant.ownership_transferred",
            user_id=str(current_user_id),
            tenant_id=str(tenant_id),
            old_owner_id=str(old_owner_id) if old_owner_id else None,
            new_owner_id=str(new_owner_id) if new_owner_id else None,
        )

        # Get new owner name
        owner_name = None
        if new_owner_id:
            name_result = await self.db.execute(
                select(User.full_name).where(User.id == new_owner_id)
            )
            owner_name = name_result.scalar_one_or_none()

        return {"owner_name": owner_name}

    async def remove_membership(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        result = await self.db.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise NotFoundError("Membership", f"tenant={tenant_id}, user={user_id}")

        await self.db.delete(membership)
        await self.db.flush()

    async def reactivate_archived_account(
        self, user_id: uuid.UUID, current_user: "User",
    ) -> dict:
        """Reactivate an archived account (superadmin only)."""
        from datetime import timedelta

        if not settings.data_retention_allow_reactivation:
            raise ForbiddenError("Accountreactivatie is uitgeschakeld in de configuratie")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        if user.anonymized_at is not None:
            raise ConflictError("Dit account is geanonimiseerd en kan niet worden hersteld")

        if user.archived_at is None:
            raise ConflictError("Dit account is niet gearchiveerd")

        # Check reactivation window
        from datetime import timezone
        window = timedelta(days=settings.data_retention_reactivation_window_days)
        archived_at_utc = user.archived_at if user.archived_at.tzinfo else user.archived_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > archived_at_utc + window:
            raise ConflictError(
                "De reactivatieperiode is verlopen. "
                "Dit account kan niet meer worden hersteld."
            )

        # Reactivate
        user.is_active = True
        user.archived_at = None
        user.archived_by = None

        await self.db.flush()

        # Audit log
        audit = AuditService(self.db)
        await audit.log(
            "account.reactivated",
            user_id=user.id,
            actor_id=str(current_user.id),
            actor_email=current_user.email,
        )
        logger.info(
            "account.reactivated",
            user_id=str(user.id),
            actor_id=str(current_user.id),
        )

        return await self.get_user_detail(user_id)
