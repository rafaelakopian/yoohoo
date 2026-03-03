import uuid
from datetime import datetime

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import update as sa_update

from app.core.email import send_email_safe
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security_emails import build_2fa_admin_reset_email
from app.modules.platform.auth.audit import AuditService
from app.modules.platform.auth.constants import Role
from app.modules.platform.auth.dependencies import is_platform_user
from app.modules.platform.auth.models import (
    AuditLog,
    PermissionGroup,
    TenantMembership,
    User,
    UserGroupAssignment,
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

        user_counts = await self.db.execute(
            select(
                func.count(User.id).label("total"),
                func.count(User.id).filter(User.is_active).label("active"),
            )
        )
        urow = user_counts.one()

        return {
            "total_tenants": row.total,
            "active_tenants": row.active,
            "provisioned_tenants": row.provisioned,
            "total_users": urow.total,
            "active_users": urow.active,
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
                "school_name": tenant.settings.school_name,
                "school_address": tenant.settings.school_address,
                "school_phone": tenant.settings.school_phone,
                "school_email": tenant.settings.school_email,
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
                "role": m.role,
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

    async def list_users(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        # Base filter for both count and data queries
        filters = []
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_filter = f"%{escaped}%"
            filters.append(
                (User.email.ilike(search_filter)) | (User.full_name.ilike(search_filter))
            )
        if is_active is not None:
            filters.append(User.is_active == is_active)

        # Total count
        count_query = select(func.count(User.id))
        for f in filters:
            count_query = count_query.where(f)
        total = (await self.db.execute(count_query)).scalar() or 0

        # Data query
        query = select(User).options(selectinload(User.memberships))
        for f in filters:
            query = query.where(f)
        query = query.order_by(User.full_name).offset(skip).limit(limit)
        result = await self.db.execute(query)
        users = result.scalars().all()

        items = [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "is_superadmin": u.is_superadmin,
                "email_verified": u.email_verified,
                "membership_count": len(u.memberships),
                "created_at": u.created_at,
            }
            for u in users
        ]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def update_user(self, user_id: uuid.UUID, data: dict) -> dict:
        """Update user fields (admin). Returns updated user detail."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        if "email" in data and data["email"] is not None and data["email"] != user.email:
            # Check uniqueness
            existing = await self.db.execute(
                select(User).where(User.email == data["email"], User.id != user_id)
            )
            if existing.scalar_one_or_none():
                raise ConflictError(f"E-mailadres '{data['email']}' is al in gebruik")
            user.email = data["email"]

        if "full_name" in data and data["full_name"] is not None:
            user.full_name = data["full_name"]

        if "is_active" in data and data["is_active"] is not None:
            user.is_active = data["is_active"]

        if "email_verified" in data and data["email_verified"] is not None:
            user.email_verified = data["email_verified"]

        await self.db.flush()
        return await self.get_user_detail(user_id)

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
                "role": m.role,
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

    async def reset_user_2fa(
        self, user_id: uuid.UUID, current_user: "User",
    ) -> dict:
        """Reset 2FA for a user. Revokes all active sessions. Sends notification email."""
        from app.modules.platform.auth.models import RefreshToken

        # Self-protection
        if user_id == current_user.id:
            raise ForbiddenError("Je kunt je eigen 2FA niet resetten via het admin-panel")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        if not user.totp_enabled:
            raise ConflictError("2FA is niet ingeschakeld voor deze gebruiker")

        # Clear 2FA data
        user.totp_enabled = False
        user.totp_secret_encrypted = None
        user.backup_codes_hash = None

        # Revoke all active sessions
        await self.db.execute(
            sa_update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )

        await self.db.flush()

        # Audit log
        audit = AuditService(self.db)
        await audit.log(
            "user.2fa_reset_by_admin",
            user_id=user.id,
            actor_id=str(current_user.id),
            actor_email=current_user.email,
            target_user_id=str(user.id),
            target_email=user.email,
        )
        logger.info(
            "admin.2fa_reset",
            target_user_id=str(user.id),
            actor_id=str(current_user.id),
        )

        # Send notification email to the user
        try:
            subject, html = build_2fa_admin_reset_email(user.full_name)
            await send_email_safe(user.email, subject, html)
        except Exception:
            logger.warning(
                "security_email.failed",
                action="2fa_admin_reset",
                user_id=str(user.id),
                exc_info=True,
            )

        return await self.get_user_detail(user_id)

    async def list_audit_logs(
        self,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
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

    async def add_membership(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID,
        role: Role | None = None, group_id: uuid.UUID | None = None,
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
                "Platformgebruikers kunnen niet als schoollid worden toegevoegd"
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
            role=role,
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
            "role": membership.role,
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
                    "Platformgebruikers kunnen geen eigenaar van een school zijn"
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
                    "Gebruiker moet lid zijn van de school om eigenaar te worden"
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
